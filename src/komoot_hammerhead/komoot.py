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
