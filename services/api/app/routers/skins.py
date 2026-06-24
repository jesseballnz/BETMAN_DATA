from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.compliance import get_compliance_rule

router = APIRouter(prefix="/skins", tags=["skins"])


class SkinAssets(BaseModel):
    logo: str | None = None
    logo_dark: str | None = None
    favicon: str | None = None
    background: str | None = None
    sponsor_logo: str | None = None
    watermark: str | None = None


class ActiveAd(BaseModel):
    slot: str
    creative_url: str
    click_url: str | None
    dimensions: str | None


class TenantFeed(BaseModel):
    feed_id: int
    name: str
    url: str
    quality: str


class SkinCompliance(BaseModel):
    jurisdiction: str
    age_gate_minimum: int
    responsible_gambling_message: str
    support_url: str
    support_phone: str
    advisory: str
    product_positioning: str


class SkinResponse(BaseModel):
    tenant: str
    skin_id: int
    skin_name: str
    context_type: str
    context_ref: str | None
    config: dict
    assets: SkinAssets
    active_ads: list[ActiveAd]
    feeds: list[TenantFeed]
    compliance: SkinCompliance


@router.get("/{tenant_slug}", response_model=SkinResponse, summary="Resolve tenant skin")
async def resolve_skin(
    tenant_slug: str,
    race_class: str | None = Query(None, description="Activate class-specific skin, e.g. G1"),
    meeting_id: int | None = Query(None),
    race_id: int | None = Query(None),
):
    """
    Resolve the active skin config for a tenant, optionally scoped to a context
    (race class, meeting, or specific race). Returns the fully resolved skin —
    colors, logos, feature flags, active ad placements, and licensed feeds —
    ready to apply directly to a front-end renderer.

    Context resolution hierarchy (highest priority wins):
      race > meeting > race_class > global
    """
    # TODO: query tenants + skins + skin_contexts with priority resolution
    # TODO: resolve active ads from ad_placements
    # TODO: resolve tenant_feeds for this tenant
    compliance = get_compliance_rule("NZ")
    return SkinResponse(
        tenant=tenant_slug,
        skin_id=0,
        skin_name="Default",
        context_type="global",
        context_ref=None,
        config={
            "colors": {},
            "typography": {},
            "layout": {},
            "features": {
                "commentary_replay": True,
                "race_story": True,
                "similarity_search": False,
                "live_websocket": True,
                "show_odds": True,
            },
            "compliance": compliance,
        },
        assets=SkinAssets(),
        active_ads=[],
        feeds=[],
        compliance=SkinCompliance(**compliance),
    )


@router.get("/{tenant_slug}/ads", summary="Active ad placements")
async def get_skin_ads(
    tenant_slug: str,
    slot: str = Query(..., description="Slot code, e.g. pre_race_banner"),
):
    """Get the active ad placement for a specific slot within a tenant's skin."""
    return {"tenant": tenant_slug, "slot": slot, "ad": None}
