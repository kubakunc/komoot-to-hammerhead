from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from komootgpx.api import KomootApi
from komootgpx.gpxcompiler import GpxCompiler

from .config import settings
from . import db

log = logging.getLogger(__name__)


@dataclass
class TourInfo:
    id: str
    name: str
    sport: str
    distance_km: float


@dataclass
class TourData:
    coordinates: list[dict[str, float]]
    elevation: list[float]
    duration_s: int
    elevation_up: float
    elevation_down: float
    difficulty: str | None = None
    surfaces: list[dict[str, str | float]] | None = None
    map_url: str | None = None


class KomootClient:
    def __init__(self) -> None:
        self._api = KomootApi(debug=False)
        self._logged_in = False

    def login(self) -> None:
        if self._logged_in:
            return
        # Always do a fresh login (KomootGPX's token-reuse path has a bug
        # where display_name isn't set, causing an AttributeError)
        user_id, token, display_name = self._api.login(
            email=settings.komoot_email,
            password=settings.komoot_password,
        )
        db.save_token("komoot", token, user_id=str(user_id))
        self._logged_in = True
        log.info("Komoot login OK — user: %s (%s)", display_name, user_id)

    def list_tours(self) -> list[TourInfo]:
        self.login()
        tours_dict = self._api.fetch_tours(
            tour_type=settings.komoot_tour_type, silent=True
        )
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.sync_days)
        result: list[TourInfo] = []
        for tour_id, tour in tours_dict.items():
            tour_date = datetime.fromisoformat(tour.get("date", ""))
            if tour_date < cutoff:
                continue
            name = tour.get("name", "")
            sport = tour.get("sport", "")
            distance = tour.get("distance", 0) / 1000.0  # m -> km
            result.append(TourInfo(id=str(tour_id), name=name, sport=sport, distance_km=round(distance, 2)))
        return result

    def download_gpx(self, tour_id: str) -> bytes:
        self.login()
        tour = self._api.fetch_tour(tour_id)
        compiler = GpxCompiler(tour=tour, api=self._api, no_poi=False, max_desc_length=-1)
        gpx_str = compiler.generate()
        return gpx_str.encode("utf-8")

    def get_tour(self, tour_id: str) -> TourInfo:
        self.login()
        tour = self._api.fetch_tour(tour_id)
        name = tour.get("name", "")
        sport = tour.get("sport", "")
        distance = tour.get("distance", 0) / 1000.0
        return TourInfo(id=str(tour_id), name=name, sport=sport, distance_km=round(distance, 2))

    def get_tour_data(self, tour_id: str) -> TourData:
        self.login()
        tour = self._api.fetch_tour(tour_id)
        coords = []
        altitudes = []
        
        if "_embedded" in tour and "coordinates" in tour["_embedded"]:
            items = tour["_embedded"]["coordinates"]["items"]
            for item in items:
                coords.append({"lat": item["lat"], "lng": item["lng"]})
                altitudes.append(item["alt"])
                
        map_url = None
        if "vector_map_image" in tour:
            map_url = tour["vector_map_image"].get("src")
        elif "map_image" in tour:
            map_url = tour["map_image"].get("src")
            # If templated, use a reasonable default size
            if tour["map_image"].get("templated"):
                map_url = map_url.replace("{width}", "600").replace("{height}", "400").replace("{crop}", "false")

        difficulty = tour.get("difficulty", {}).get("grade")
        duration = tour.get("duration", 0)
        up = tour.get("elevation_up", 0)
        down = tour.get("elevation_down", 0)
        surfaces = tour.get("summary", {}).get("surfaces", [])

        return TourData(
            coordinates=coords,
            elevation=altitudes,
            duration_s=int(duration),
            elevation_up=float(up),
            elevation_down=float(down),
            difficulty=difficulty,
            surfaces=surfaces,
            map_url=map_url
        )
