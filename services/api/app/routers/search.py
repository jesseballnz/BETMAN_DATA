from fastapi import APIRouter, Query, Response

router = APIRouter(prefix="/search", tags=["search"])

_NOT_IMPLEMENTED = Response(
    status_code=501,
    content='{"detail":"Search indexing is not yet implemented"}',
    media_type="application/json",
)


@router.get("/ocr", summary="Search OCR observations")
async def search_ocr(
    q: str = Query(..., min_length=1, description="Search text"),
    race_class: str | None = Query(None),
    date: str | None = Query(None),
    limit: int = Query(20, le=100),
):
    """
    Full-text search over OCR-extracted text from video frames.
    Not yet implemented — OCR full-text index is pending.
    """
    return _NOT_IMPLEMENTED


@router.get("/transcripts", summary="Search commentary transcripts")
async def search_transcripts(
    q: str = Query(..., min_length=1),
    race_class: str | None = Query(None),
    date: str | None = Query(None),
    scene: str | None = Query(None, description="live_race, parade_ring, barriers, etc."),
    limit: int = Query(20, le=100),
):
    """
    Full-text search over ASR-transcribed commentary segments.
    Not yet implemented — transcript full-text index is pending.
    """
    return _NOT_IMPLEMENTED


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
