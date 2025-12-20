from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PredictionItem(BaseModel):
    horse_number: int
    horse_id: Optional[str] = None
    horse_name: Optional[str] = None
    predicted_rank: int
    probability: float
    odds: Optional[float] = None
    popularity: Optional[int] = None


class RecommendedBet(BaseModel):
    bet_type: str
    detail: str
    confidence: str


class PredictionResult(BaseModel):
    predictions: list[PredictionItem]
    recommended_bets: list[RecommendedBet]


class PredictionResponse(BaseModel):
    prediction_id: int
    race_id: str
    model_version: str
    created_at: datetime
    results: PredictionResult

    class Config:
        from_attributes = True


class CreatePredictionRequest(BaseModel):
    race_id: str


class HistoryBase(BaseModel):
    bet_type: str = Field(..., description="Bet type (単勝, 馬連, etc.)")
    bet_detail: str = Field(..., description="Bet detail (e.g., '5' or '1-3')")
    bet_amount: Optional[int] = Field(None, description="Bet amount in yen")


class CreateHistoryRequest(HistoryBase):
    prediction_id: int


class HistoryItem(HistoryBase):
    id: int
    prediction_id: int
    is_hit: Optional[bool] = None
    payout: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class HistoryRace(BaseModel):
    race_id: str
    date: str
    race_name: Optional[str] = None


class HistoryWithRace(HistoryItem):
    race: Optional[HistoryRace] = None


class HistorySummary(BaseModel):
    total_bets: int
    total_hits: int
    hit_rate: float
    total_bet_amount: int
    total_payout: int
    roi: float


class HistoryListResponse(BaseModel):
    total: int
    summary: HistorySummary
    history: list[HistoryItem]


class UpdateHistoryResultRequest(BaseModel):
    is_hit: bool
    payout: Optional[int] = None


class HistoryUpdateResponse(BaseModel):
    id: int
    is_hit: bool
    payout: Optional[int] = None
    message: str


class AccuracyStats(BaseModel):
    top1: float
    top3: float
    top5: float = 0.0


class AccuracyByCategory(BaseModel):
    top1: float
    top3: float


class StatsResponse(BaseModel):
    period: str
    accuracy: AccuracyStats
    by_grade: dict[str, AccuracyByCategory] = {}
    by_track: dict[str, AccuracyByCategory] = {}
