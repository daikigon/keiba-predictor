from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import prediction_service

router = APIRouter()


@router.post("")
async def create_prediction(
    race_id: str = Query(..., description="Race ID to predict"),
    db: Session = Depends(get_db),
):
    """Create prediction for a race"""
    try:
        prediction = prediction_service.create_prediction(db, race_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "prediction_id": prediction.id,
        "race_id": prediction.race_id,
        "model_version": prediction.model_version,
        "created_at": prediction.created_at.isoformat(),
        "results": prediction.results_json,
    }


@router.get("/{race_id}")
async def get_prediction(
    race_id: str,
    db: Session = Depends(get_db),
):
    """Get prediction for a race"""
    prediction = prediction_service.get_prediction_by_race(db, race_id)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    return {
        "prediction_id": prediction.id,
        "race_id": prediction.race_id,
        "model_version": prediction.model_version,
        "created_at": prediction.created_at.isoformat(),
        "results": prediction.results_json,
    }
