from fastapi import APIRouter, Query

router = APIRouter(prefix="/feeds", tags=["feeds"])


@router.get("", summary="List all feeds")
async def list_feeds():
    """List all configured live media feeds with current session info."""
    # TODO: query feeds table, join to stream_sessions for current session
    return {
        "feeds": [
            {
                "id": 1,
                "name": "Trackside 1",
                "url": "https://trackside-nz.akamaized.net/hls/live/2115595/Trackside1/OnDemand/master.m3u8",
                "active": True,
                "current_session_id": None,
            },
            {
                "id": 2,
                "name": "Trackside 2",
                "url": "https://trackside-nz.akamaized.net/hls/live/2115596/Trackside2/OnDemand/master.m3u8",
                "active": True,
                "current_session_id": None,
            },
        ]
    }


@router.get("/{feed_id}", summary="Get feed detail")
async def get_feed(feed_id: int):
    """Get a single feed with recent session and segment info."""
    return {"feed_id": feed_id}
