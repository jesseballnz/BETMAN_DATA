from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.assistant_service import resolve_plan
from app.compliance import RG_DISCLAIMER
from app.db import execute_readonly_query

router = APIRouter(prefix="/assistant", tags=["assistant"])


class AssistantQueryRequest(BaseModel):
    question: str = Field(min_length=3)


@router.post("/query")
async def query_assistant(request: Request, payload: AssistantQueryRequest):
    try:
        plan = await resolve_plan(payload.question)
        rows = await execute_readonly_query(
            request,
            plan.sql,
            plan.params,
            statement_timeout_ms=1_500,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    summary = plan.summary
    if rows:
        summary = f"{plan.summary} Returned {len(rows)} rows."
    else:
        summary = f"{plan.summary} No matching rows were found."

    return {
        "question": payload.question,
        "provider": plan.provider,
        "sql": plan.sql,
        "parameters": plan.params,
        "rows": rows,
        "summary": summary,
        "confidence": plan.confidence,
        "chart": plan.chart or {"type": "table"},
        "disclaimer": RG_DISCLAIMER,
    }
