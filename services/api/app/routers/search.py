from fastapi import APIRouter, Query, Request, Response

from app.db import fetch_all

router = APIRouter(prefix="/search", tags=["search"])

_NOT_IMPLEMENTED = Response(
    status_code=501,
    content='{"detail":"Search indexing is not yet implemented"}',
    media_type="application/json",
)


@router.get("/ocr", summary="Search OCR observations")
async def search_ocr(
    request: Request,
    q: str = Query(..., min_length=1, description="Search text"),
    race_class: str | None = Query(None),
    date: str | None = Query(None),
    days: int = Query(60, ge=1, le=365, description="Lookback window in days"),
    limit: int = Query(20, le=100),
):
    """
    Full-text search over OCR-extracted text from video frames.
    """
    rows = await fetch_all(
        request,
        """
        SELECT
            'ocr' AS source,
            COALESCE(oo.observation_type, 'screen text') AS label,
            oo.detected_text AS snippet,
            oo.normalized_text,
            oo.frame_timestamp::text AS occurred_at,
            oo.confidence::float AS confidence,
            m.track_name,
            m.meeting_date::text AS meeting_date,
            r.race_number,
            r.race_class_code
        FROM ocr_observations oo
        LEFT JOIN media_segments ms ON ms.id = oo.segment_id
        LEFT JOIN clips c ON c.feed_id = ms.feed_id
          AND oo.frame_timestamp BETWEEN c.started_at AND c.ended_at
        LEFT JOIN races r ON r.id = c.race_id
        LEFT JOIN meetings m ON m.id = r.meeting_id
        WHERE (oo.detected_text ILIKE '%' || $1 || '%'
            OR oo.normalized_text ILIKE '%' || $1 || '%'
            OR oo.observation_type ILIKE '%' || $1 || '%')
          AND oo.frame_timestamp >= now() - make_interval(days => $2::int)
          AND ($3::text IS NULL OR r.race_class_code = $3::text OR r.race_class_group = $3::text)
          AND ($4::date IS NULL OR m.meeting_date = $4::date OR oo.frame_timestamp::date = $4::date)
        ORDER BY oo.frame_timestamp DESC
        LIMIT $5
        """,
        q,
        days,
        race_class,
        date,
        limit,
    )
    return {"query": q, "results": rows, "days": days}


@router.get("/transcripts", summary="Search commentary transcripts")
async def search_transcripts(
    request: Request,
    q: str = Query(..., min_length=1),
    race_class: str | None = Query(None),
    date: str | None = Query(None),
    scene: str | None = Query(None, description="live_race, parade_ring, barriers, etc."),
    days: int = Query(60, ge=1, le=365, description="Lookback window in days"),
    limit: int = Query(20, le=100),
):
    """
    Full-text search over ASR-transcribed commentary segments.
    """
    rows = await fetch_all(
        request,
        """
        SELECT
            'transcript' AS source,
            COALESCE(ae.event_type, 'commentary') AS label,
            ts.text AS snippet,
            ts.started_at::text AS occurred_at,
            ts.ended_at::text AS ended_at,
            ts.confidence::float AS confidence,
            ts.race_offset_ms,
            m.track_name,
            m.meeting_date::text AS meeting_date,
            r.race_number,
            r.race_class_code
        FROM transcript_segments ts
        LEFT JOIN audio_events ae ON ae.id = ts.audio_event_id
        LEFT JOIN races r ON r.id = ts.race_id
        LEFT JOIN meetings m ON m.id = r.meeting_id
        WHERE ts.text ILIKE '%' || $1 || '%'
          AND ts.started_at >= now() - make_interval(days => $2::int)
          AND ($3::text IS NULL OR r.race_class_code = $3::text OR r.race_class_group = $3::text)
          AND ($4::date IS NULL OR m.meeting_date = $4::date OR ts.started_at::date = $4::date)
          AND ($5::text IS NULL OR ae.event_type = $5::text)
        ORDER BY ts.started_at DESC
        LIMIT $6
        """,
        q,
        days,
        race_class,
        date,
        scene,
        limit,
    )
    return {"query": q, "results": rows, "days": days}


@router.get("/similar", summary="Find similar races via embedding")
async def search_similar(
    race_id: int = Query(...),
    limit: int = Query(10, le=50),
    embedding_type: str = Query("combined", description="commentary, audio, visual, combined"),
):
    """
    Find races with a similar audio/commentary arc to the given race using
    vector embedding similarity (pgvector cosine distance).
    Not yet implemented — embedding pipeline is pending.
    """
    return _NOT_IMPLEMENTED
