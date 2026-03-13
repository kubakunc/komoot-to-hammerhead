from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import db
from .config import settings
from .komoot import KomootClient
from .sync import sync_all, sync_one

app = FastAPI(
    title="Komoot → Hammerhead Sync API",
    version="0.1.0",
    description=(
        "Syncs planned routes from Komoot to Hammerhead Karoo. "
        "Authenticates to both services automatically and uploads GPX files "
        "to the Hammerhead dashboard. Only routes created within the last "
        "`SYNC_DAYS` (default 3) are considered."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(x_api_key: str = Header(description="Shared secret matching `API_SECRET` env var")) -> None:
    if not settings.api_secret or x_api_key != settings.api_secret:
        raise HTTPException(status_code=401, detail="Invalid API key")


class SyncResponse(BaseModel):
    synced: int
    skipped: int
    failed: int
    errors: list[str]


class StatusResponse(BaseModel):
    total: int
    success: int
    failed: int


class TourItem(BaseModel):
    id: str
    name: str
    sport: str
    distance_km: float
    synced: bool


class TourDataResponse(BaseModel):
    coordinates: list[dict[str, float]]
    elevation: list[float]
    map_url: str | None = None


class RouteRecord(BaseModel):
    komoot_tour_id: str
    name: str | None
    sport_type: str | None
    distance_km: float | None
    hammerhead_id: str | None
    synced_at: str
    status: str


class RouteUpdate(BaseModel):
    name: str | None = None
    sport_type: str | None = None
    distance_km: float | None = None
    hammerhead_id: str | None = None
    status: str | None = None


class DeleteResponse(BaseModel):
    deleted: bool


@app.on_event("startup")
def startup() -> None:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    db.init_db()


@app.post(
    "/sync",
    response_model=SyncResponse,
    summary="Sync all new routes",
    description=(
        "Fetches planned routes from Komoot created in the last `SYNC_DAYS`, "
        "filters out already-synced ones, and uploads each new route as GPX "
        "to the Hammerhead dashboard."
    ),
    dependencies=[Depends(verify_api_key)],
)
def post_sync() -> SyncResponse:
    result = sync_all()
    return SyncResponse(
        synced=result.synced,
        skipped=result.skipped,
        failed=result.failed,
        errors=result.errors or [],
    )


@app.post(
    "/sync/{tour_id}",
    response_model=SyncResponse,
    summary="Sync a single route",
    description=(
        "Downloads the GPX for the given Komoot tour ID and uploads it to "
        "Hammerhead. Skips if already synced unless `force=true`."
    ),
    dependencies=[Depends(verify_api_key)],
)
def post_sync_one(tour_id: str, force: bool = False) -> SyncResponse:
    result = sync_one(tour_id, force=force)
    return SyncResponse(
        synced=result.synced,
        skipped=result.skipped,
        failed=result.failed,
        errors=result.errors or [],
    )


@app.get(
    "/status",
    response_model=StatusResponse,
    summary="Sync statistics",
    description="Returns counts of total, successful, and failed route syncs.",
    dependencies=[Depends(verify_api_key)],
)
def get_status() -> StatusResponse:
    stats = db.get_stats()
    return StatusResponse(**stats)


@app.get(
    "/routes",
    response_model=list[RouteRecord],
    summary="List synced routes",
    description="Returns synced routes ordered by most recent first.",
    dependencies=[Depends(verify_api_key)],
)
def get_routes(
    limit: int = Query(50, ge=1, le=500, description="Max routes to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> list[RouteRecord]:
    return [RouteRecord(**r) for r in db.list_routes(limit, offset)]


@app.get(
    "/routes/{tour_id}",
    response_model=RouteRecord,
    summary="Get a single route",
    description="Returns details of a synced route by its Komoot tour ID.",
    dependencies=[Depends(verify_api_key)],
)
def get_route(tour_id: str) -> RouteRecord:
    route = db.get_route(tour_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return RouteRecord(**route)


@app.patch(
    "/routes/{tour_id}",
    response_model=RouteRecord,
    summary="Update a route",
    description="Updates mutable fields of a synced route record. Only provided fields are changed.",
    dependencies=[Depends(verify_api_key)],
)
def patch_route(tour_id: str, body: RouteUpdate) -> RouteRecord:
    if not db.get_route(tour_id):
        raise HTTPException(status_code=404, detail="Route not found")
    updated = db.update_route(tour_id, **body.model_dump(exclude_none=True))
    return RouteRecord(**updated)


@app.delete(
    "/routes/{tour_id}",
    response_model=DeleteResponse,
    summary="Delete a route",
    description="Removes a synced route record from the database. Does not delete the route from Hammerhead.",
    dependencies=[Depends(verify_api_key)],
)
def delete_route(tour_id: str) -> DeleteResponse:
    deleted = db.delete_route(tour_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Route not found")
    return DeleteResponse(deleted=True)


@app.get(
    "/tours",
    response_model=list[TourItem],
    summary="List available Komoot tours",
    description=(
        "Fetches planned tours from Komoot (last `SYNC_DAYS`) and annotates "
        "each with whether it has already been synced to Hammerhead."
    ),
    dependencies=[Depends(verify_api_key)],
)
def get_tours() -> list[TourItem]:
    komoot = KomootClient()
    tours = komoot.list_tours()
    synced_ids = db.get_synced_ids()
    return [
        TourItem(
            id=t.id,
            name=t.name,
            sport=t.sport,
            distance_km=t.distance_km,
            synced=t.id in synced_ids,
        )
        for t in tours
    ]


@app.get(
    "/tours/{tour_id}/data",
    response_model=TourDataResponse,
    summary="Get tour visualization data",
    description="Returns coordinates and elevation profile for a tour.",
    dependencies=[Depends(verify_api_key)],
)
def get_tour_data_endpoint(tour_id: str) -> TourDataResponse:
    komoot = KomootClient()
    data = komoot.get_tour_data(tour_id)
    return TourDataResponse(
        coordinates=[{"lat": c["lat"], "lng": c["lng"]} for c in data.coordinates],
        elevation=data.elevation,
        map_url=data.map_url,
    )

