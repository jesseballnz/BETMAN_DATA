"""
Admin router — full CRUD for tenants, skins, assets, ad slots,
weather stations, external API keys, and tenant feed assignments.

All routes require an admin-scoped API key (enforced by TenantMiddleware).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Tenants ───────────────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str
    slug: str
    contact_email: str | None = None
    license_type: str = "full"
    license_expires_at: str | None = None


@router.get("/tenants", summary="List tenants")
async def list_tenants():
    return {"tenants": []}


@router.post("/tenants", status_code=201, summary="Create tenant")
async def create_tenant(body: TenantCreate):
    # TODO: insert into tenants table
    return {"id": 1, **body.model_dump()}


@router.get("/tenants/{tenant_id}", summary="Get tenant")
async def get_tenant(tenant_id: int):
    raise HTTPException(status_code=404, detail="Tenant not found")


@router.patch("/tenants/{tenant_id}", summary="Update tenant")
async def update_tenant(tenant_id: int, body: dict):
    return {"tenant_id": tenant_id, "updated": body}


@router.delete("/tenants/{tenant_id}", status_code=204, summary="Deactivate tenant")
async def deactivate_tenant(tenant_id: int):
    return None


# ── Skins ─────────────────────────────────────────────────────────────────────

class SkinCreate(BaseModel):
    name: str
    slug: str
    is_default: bool = False
    config_json: dict = {}


@router.get("/tenants/{tenant_id}/skins", summary="List skins for tenant")
async def list_skins(tenant_id: int):
    return {"tenant_id": tenant_id, "skins": []}


@router.post("/tenants/{tenant_id}/skins", status_code=201, summary="Create skin")
async def create_skin(tenant_id: int, body: SkinCreate):
    return {"id": 1, "tenant_id": tenant_id, **body.model_dump()}


@router.get("/skins/{skin_id}", summary="Get skin detail")
async def get_skin(skin_id: int):
    raise HTTPException(status_code=404, detail="Skin not found")


@router.patch("/skins/{skin_id}", summary="Update skin config")
async def update_skin(skin_id: int, body: dict):
    return {"skin_id": skin_id, "updated": body}


@router.post("/skins/{skin_id}/set-default", summary="Set as tenant default skin")
async def set_default_skin(skin_id: int):
    return {"skin_id": skin_id, "is_default": True}


# ── Skin Assets ───────────────────────────────────────────────────────────────

@router.get("/skins/{skin_id}/assets", summary="List skin assets")
async def list_skin_assets(skin_id: int):
    return {"skin_id": skin_id, "assets": []}


@router.post("/skins/{skin_id}/assets", status_code=201, summary="Upload skin asset")
async def upload_skin_asset(skin_id: int):
    # Accepts multipart/form-data with asset_type, label, and file
    # TODO: stream upload to object storage, write skin_assets row
    return {"skin_id": skin_id, "asset_id": 1}


@router.delete("/skins/{skin_id}/assets/{asset_id}", status_code=204, summary="Delete asset")
async def delete_skin_asset(skin_id: int, asset_id: int):
    return None


# ── Skin Contexts ─────────────────────────────────────────────────────────────

class SkinContextCreate(BaseModel):
    context_type: str
    context_ref: str | None = None
    priority: int = 0


@router.get("/skins/{skin_id}/contexts", summary="List skin contexts")
async def list_skin_contexts(skin_id: int):
    return {"skin_id": skin_id, "contexts": []}


@router.post("/skins/{skin_id}/contexts", status_code=201, summary="Add skin context")
async def add_skin_context(skin_id: int, body: SkinContextCreate):
    return {"skin_id": skin_id, **body.model_dump()}


@router.delete("/skins/{skin_id}/contexts/{ctx_id}", status_code=204, summary="Remove context")
async def remove_skin_context(skin_id: int, ctx_id: int):
    return None


# ── Ad Slots & Placements ─────────────────────────────────────────────────────

@router.get("/ad-slots", summary="List ad slot types")
async def list_ad_slots():
    return {
        "slots": [
            {"code": "replay_overlay_top",      "dimensions": "970x60",  "display_context": "replay"},
            {"code": "pre_race_banner",          "dimensions": "728x90",  "display_context": "pre_race"},
            {"code": "results_sidebar",          "dimensions": "300x250", "display_context": "results"},
            {"code": "race_card_footer",         "dimensions": "728x90",  "display_context": "race_card"},
            {"code": "commentary_interstitial",  "dimensions": "640x480", "display_context": "replay"},
        ]
    }


class AdPlacementCreate(BaseModel):
    slot_type_id: int
    asset_id: int | None = None
    label: str | None = None
    click_url: str | None = None
    active_from: str | None = None
    active_until: str | None = None
    priority: int = 0


@router.get("/skins/{skin_id}/ads", summary="List ad placements")
async def list_ad_placements(skin_id: int):
    return {"skin_id": skin_id, "placements": []}


@router.post("/skins/{skin_id}/ads", status_code=201, summary="Create ad placement")
async def create_ad_placement(skin_id: int, body: AdPlacementCreate):
    return {"skin_id": skin_id, "placement_id": 1, **body.model_dump()}


@router.patch("/skins/{skin_id}/ads/{placement_id}", summary="Update placement")
async def update_ad_placement(skin_id: int, placement_id: int, body: dict):
    return {"placement_id": placement_id, "updated": body}


@router.delete("/skins/{skin_id}/ads/{placement_id}", status_code=204, summary="Remove placement")
async def delete_ad_placement(skin_id: int, placement_id: int):
    return None


# ── Tenant Feeds ──────────────────────────────────────────────────────────────

class TenantFeedAssign(BaseModel):
    feed_id: int
    override_url: str | None = None
    quality_preference: str = "auto"


@router.get("/tenants/{tenant_id}/feeds", summary="List tenant feeds")
async def list_tenant_feeds(tenant_id: int):
    return {"tenant_id": tenant_id, "feeds": []}


@router.post("/tenants/{tenant_id}/feeds", status_code=201, summary="Assign feed to tenant")
async def assign_tenant_feed(tenant_id: int, body: TenantFeedAssign):
    # Also invalidates the TenantRouter Redis cache for this feed
    return {"tenant_id": tenant_id, **body.model_dump()}


@router.patch("/tenants/{tenant_id}/feeds/{feed_id}", summary="Update tenant feed config")
async def update_tenant_feed(tenant_id: int, feed_id: int, body: dict):
    return {"tenant_id": tenant_id, "feed_id": feed_id, "updated": body}


@router.delete("/tenants/{tenant_id}/feeds/{feed_id}", status_code=204, summary="Remove feed from tenant")
async def remove_tenant_feed(tenant_id: int, feed_id: int):
    return None


# ── Weather Stations ──────────────────────────────────────────────────────────

class WeatherStationCreate(BaseModel):
    track_name: str
    station_id: str
    api_key_config_id: int
    label: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    elevation_m: float | None = None


class ProbeCreate(BaseModel):
    probe_label: str
    position_description: str | None = None
    depth_mm: int | None = None
    distance_from_finish_m: int | None = None
    zone: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@router.get("/weather-stations", summary="List weather stations")
async def list_weather_stations():
    return {"stations": []}


@router.post("/weather-stations", status_code=201, summary="Add weather station")
async def create_weather_station(body: WeatherStationCreate):
    return {"id": 1, **body.model_dump()}


@router.get("/weather-stations/{station_id}", summary="Get station + probes")
async def get_weather_station(station_id: int):
    raise HTTPException(status_code=404, detail="Station not found")


@router.patch("/weather-stations/{station_id}", summary="Update station config")
async def update_weather_station(station_id: int, body: dict):
    return {"station_id": station_id, "updated": body}


@router.delete("/weather-stations/{station_id}", status_code=204, summary="Deactivate station")
async def deactivate_weather_station(station_id: int):
    return None


@router.get("/weather-stations/{station_id}/probes", summary="List probes")
async def list_probes(station_id: int):
    return {"station_id": station_id, "probes": []}


@router.post("/weather-stations/{station_id}/probes", status_code=201, summary="Add probe")
async def add_probe(station_id: int, body: ProbeCreate):
    return {"station_id": station_id, **body.model_dump()}


@router.patch("/weather-stations/{station_id}/probes/{probe_id}", summary="Update probe")
async def update_probe(station_id: int, probe_id: int, body: dict):
    return {"probe_id": probe_id, "updated": body}


# ── External API Keys ─────────────────────────────────────────────────────────

class ApiKeyCreate(BaseModel):
    service_name: str
    key_name: str
    api_key: str
    endpoint_url: str | None = None
    extra_config_json: dict = {}


@router.get("/api-keys", summary="List API key configs (keys redacted)")
async def list_api_keys():
    return {"api_keys": []}


@router.post("/api-keys", status_code=201, summary="Add API key config")
async def create_api_key(body: ApiKeyCreate):
    # Encrypt body.api_key with platform_master_key before storing
    # TODO: implement encryption
    return {"id": 1, "service_name": body.service_name, "key_name": body.key_name}


@router.patch("/api-keys/{key_id}", summary="Update API key")
async def update_api_key(key_id: int, body: dict):
    return {"key_id": key_id, "updated": body}


@router.delete("/api-keys/{key_id}", status_code=204, summary="Deactivate key")
async def deactivate_api_key(key_id: int):
    return None


@router.post("/api-keys/{key_id}/test", summary="Test external service connectivity")
async def test_api_key(key_id: int):
    """Decrypts the key and makes a test request to the configured endpoint."""
    # TODO: implement per-service connectivity test
    return {"key_id": key_id, "status": "ok", "message": "Connectivity test not yet implemented"}
