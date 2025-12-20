from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class HorseBase(BaseModel):
    horse_id: str
    name: str
    sex: str
    birth_year: int


class HorseResponse(HorseBase):
    father: Optional[str] = None
    mother: Optional[str] = None
    mother_father: Optional[str] = None
    trainer: Optional[str] = None

    class Config:
        from_attributes = True


class JockeyBase(BaseModel):
    jockey_id: str
    name: str


class JockeyResponse(JockeyBase):
    win_rate: Optional[float] = None
    place_rate: Optional[float] = None
    show_rate: Optional[float] = None

    class Config:
        from_attributes = True


class EntryBase(BaseModel):
    horse_number: int
    frame_number: Optional[int] = None
    weight: Optional[float] = None
    horse_weight: Optional[int] = None
    weight_diff: Optional[int] = None
    odds: Optional[float] = None
    popularity: Optional[int] = None


class EntryResponse(EntryBase):
    id: int
    race_id: str
    horse_id: Optional[str] = None
    horse_name: Optional[str] = None
    jockey_id: Optional[str] = None
    jockey_name: Optional[str] = None
    result: Optional[int] = None
    finish_time: Optional[str] = None
    margin: Optional[str] = None
    corner_position: Optional[str] = None
    last_3f: Optional[float] = None

    class Config:
        from_attributes = True


class RaceBase(BaseModel):
    race_id: str
    date: date
    course: str
    race_number: int
    distance: int
    track_type: str


class RaceListItem(RaceBase):
    race_name: Optional[str] = None
    grade: Optional[str] = None

    class Config:
        from_attributes = True


class RaceDetail(RaceBase):
    race_name: Optional[str] = None
    weather: Optional[str] = None
    condition: Optional[str] = None
    grade: Optional[str] = None
    entries: list[EntryResponse] = []

    class Config:
        from_attributes = True


class RaceListResponse(BaseModel):
    total: int
    races: list[RaceListItem]


class ScrapeRaceRequest(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date in YYYY-MM-DD format")
    course: Optional[str] = Field(None, description="Course name filter")


class ScrapeRaceResponse(BaseModel):
    status: str
    message: str
    races_count: int
    saved_count: int = 0
    races: list[dict] = []


class ScrapeDetailResponse(BaseModel):
    status: str
    saved: bool
    race: dict
