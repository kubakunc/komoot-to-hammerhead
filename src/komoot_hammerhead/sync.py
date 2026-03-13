from __future__ import annotations

import logging
from dataclasses import dataclass

from . import db
from .komoot import KomootClient
from .hammerhead import HammerheadClient

log = logging.getLogger(__name__)


@dataclass
class SyncResult:
    synced: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] | None = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def sync_all() -> SyncResult:
    db.init_db()
    komoot = KomootClient()
    hammerhead = HammerheadClient()
    result = SyncResult()

    tours = komoot.list_tours()
    synced_ids = db.get_synced_ids()
    new_tours = [t for t in tours if t.id not in synced_ids]

    if not new_tours:
        log.info("No new tours to sync (%d already synced)", len(synced_ids))
        result.skipped = len(tours)
        return result

    log.info("Found %d new tours to sync (out of %d total)", len(new_tours), len(tours))
    result.skipped = len(tours) - len(new_tours)

    for tour in new_tours:
        try:
            log.info("Syncing: %s (%s)", tour.name, tour.id)
            gpx = komoot.download_gpx(tour.id)
            hh_id = hammerhead.upload_gpx(tour.name, gpx)
            db.mark_synced(
                tour.id,
                hh_id,
                name=tour.name,
                sport_type=tour.sport,
                distance_km=tour.distance_km,
            )
            result.synced += 1
        except Exception as exc:
            log.error("Failed to sync tour %s: %s", tour.id, exc)
            db.mark_synced(tour.id, None, name=tour.name, status="failed")
            result.failed += 1
            result.errors.append(f"{tour.id}: {exc}")

    return result


def sync_one(tour_id: str) -> SyncResult:
    db.init_db()
    result = SyncResult()

    if db.is_synced(tour_id):
        log.info("Tour %s already synced, skipping", tour_id)
        result.skipped = 1
        return result

    komoot = KomootClient()
    hammerhead = HammerheadClient()

    try:
        gpx = komoot.download_gpx(tour_id)
        hh_id = hammerhead.upload_gpx(tour_id, gpx)
        db.mark_synced(tour_id, hh_id)
        result.synced = 1
    except Exception as exc:
        log.error("Failed to sync tour %s: %s", tour_id, exc)
        db.mark_synced(tour_id, None, status="failed")
        result.failed = 1
        result.errors.append(f"{tour_id}: {exc}")

    return result
