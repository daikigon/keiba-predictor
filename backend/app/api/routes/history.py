from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import prediction_service

router = APIRouter()


@router.get("")
async def get_history(
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get prediction history"""
    parsed_from = None
    parsed_to = None

    if from_date:
        try:
            parsed_from = datetime.fromisoformat(from_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid from_date format")

    if to_date:
        try:
            parsed_to = datetime.fromisoformat(to_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid to_date format")

    total, history_list, summary = prediction_service.get_history(
        db, from_date=parsed_from, to_date=parsed_to, limit=limit, offset=offset
    )

    return {
        "total": total,
        "summary": summary,
        "history": [
            {
                "id": h.id,
                "prediction_id": h.prediction_id,
                "bet_type": h.bet_type,
                "bet_detail": h.bet_detail,
                "bet_amount": h.bet_amount,
                "is_hit": h.is_hit,
                "payout": h.payout,
                "created_at": h.created_at.isoformat(),
            }
            for h in history_list
        ],
    }


@router.post("")
async def create_history(
    prediction_id: int = Query(..., description="Prediction ID"),
    bet_type: str = Query(..., description="Bet type (単勝, 馬連, etc.)"),
    bet_detail: str = Query(..., description="Bet detail (e.g., '5' or '1-3')"),
    bet_amount: Optional[int] = Query(None, description="Bet amount in yen"),
    db: Session = Depends(get_db),
):
    """Create history entry"""
    # Verify prediction exists
    prediction = prediction_service.get_prediction_by_id(db, prediction_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    history = prediction_service.create_history(
        db, prediction_id=prediction_id, bet_type=bet_type,
        bet_detail=bet_detail, bet_amount=bet_amount
    )

    return {
        "id": history.id,
        "prediction_id": history.prediction_id,
        "bet_type": history.bet_type,
        "bet_detail": history.bet_detail,
        "bet_amount": history.bet_amount,
        "created_at": history.created_at.isoformat(),
        "message": "History created",
    }


@router.put("/{history_id}/result")
async def update_history_result(
    history_id: int,
    is_hit: bool = Query(..., description="Whether the bet hit"),
    payout: Optional[int] = Query(None, description="Payout amount if hit"),
    db: Session = Depends(get_db),
):
    """Update history result"""
    history = prediction_service.update_history_result(
        db, history_id=history_id, is_hit=is_hit, payout=payout
    )

    if not history:
        raise HTTPException(status_code=404, detail="History not found")

    return {
        "id": history.id,
        "is_hit": history.is_hit,
        "payout": history.payout,
        "message": "Result updated",
    }
