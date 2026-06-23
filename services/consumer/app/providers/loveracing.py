import structlog
from typing import List

log = structlog.get_logger(__name__)

class LoveracingClient:
    """Client for NZTR (Love Racing)."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    async def fetch_todays_races(self) -> List[dict]:
        """Fetch today's races and return as a list of dicts mapped to NormalizedRace format."""
        log.info("loveracing.fetch_todays_races")
        # Placeholder for actual API call
        return []
