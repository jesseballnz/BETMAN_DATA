from fastapi import APIRouter, Query

from app.compliance import COMPLIANCE_RULES, RG_DISCLAIMER, get_compliance_rule

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/rules", summary="Responsible gambling and jurisdiction rules")
async def get_rules(jurisdiction: str = Query("NZ")):
    return {
        "jurisdiction": jurisdiction.upper(),
        "rule": get_compliance_rule(jurisdiction),
        "supported_jurisdictions": list(COMPLIANCE_RULES),
        "disclaimer": RG_DISCLAIMER,
    }
