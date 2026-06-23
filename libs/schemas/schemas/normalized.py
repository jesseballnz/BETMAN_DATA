from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class NormalizedRunner(BaseModel):
    provider_id: str
    provider_name: str
    name: str
    age: Optional[int] = None
    sex: Optional[str] = None
    color: Optional[str] = None

class NormalizedRaceEntry(BaseModel):
    provider_id: str
    provider_name: str
    runner_id: str
    barrier: int
    weight: float
    jockey_name: Optional[str] = None
    trainer_name: Optional[str] = None
    gear_changes: List[str] = Field(default_factory=list)

class NormalizedRace(BaseModel):
    provider_id: str
    provider_name: str
    track_name: str
    date: datetime
    race_number: int
    distance: int
    class_name: Optional[str] = None
    stake: Optional[float] = None
    track_direction: Optional[str] = None
    rail_position: Optional[str] = None
    entries: List[NormalizedRaceEntry] = Field(default_factory=list)

class NormalizedPedigree(BaseModel):
    provider_id: str
    provider_name: str
    horse_name: str
    sire_name: str
    dam_name: str
    damsire_name: Optional[str] = None
