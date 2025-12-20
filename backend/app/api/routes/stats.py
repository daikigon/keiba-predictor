from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.race import Race, Entry
from app.models.prediction import Prediction, History

router = APIRouter()


@router.get("/accuracy")
async def get_accuracy_stats(
    period: str = Query("month", description="Period: week, month, year, all"),
    db: Session = Depends(get_db),
):
    """Get prediction accuracy statistics"""
    from datetime import datetime, timedelta, timezone

    # Calculate date range based on period
    now = datetime.now(timezone.utc)
    if period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    elif period == "year":
        start_date = now - timedelta(days=365)
    else:
        start_date = None

    # Get predictions within the period
    predictions_query = select(Prediction)
    if start_date:
        predictions_query = predictions_query.where(Prediction.created_at >= start_date)

    predictions = list(db.execute(predictions_query).scalars().all())

    # Calculate accuracy metrics
    total_races = 0
    top1_hits = 0
    top3_hits = 0
    top5_hits = 0

    grade_stats = {}
    track_stats = {}

    for pred in predictions:
        race = db.get(Race, pred.race_id)
        if not race:
            continue

        results_json = pred.results_json
        if not results_json or "predictions" not in results_json:
            continue

        pred_list = results_json["predictions"]
        if not pred_list:
            continue

        # Get actual results
        entries_with_results = [
            e for e in race.entries if e.result is not None
        ]
        if not entries_with_results:
            continue

        total_races += 1

        # Get predicted top horses
        pred_top1 = pred_list[0]["horse_number"] if len(pred_list) > 0 else None
        pred_top3 = [p["horse_number"] for p in pred_list[:3]] if len(pred_list) >= 3 else []
        pred_top5 = [p["horse_number"] for p in pred_list[:5]] if len(pred_list) >= 5 else []

        # Get actual top horses
        sorted_entries = sorted(entries_with_results, key=lambda e: e.result)
        actual_top1 = sorted_entries[0].horse_number if len(sorted_entries) > 0 else None
        actual_top3 = [e.horse_number for e in sorted_entries[:3]]
        actual_top5 = [e.horse_number for e in sorted_entries[:5]]

        # Check top1 hit (predicted winner is actual winner)
        if pred_top1 == actual_top1:
            top1_hits += 1

        # Check top3 hit (predicted winner is in actual top 3)
        if pred_top1 in actual_top3:
            top3_hits += 1

        # Check top5 hit
        if pred_top1 in actual_top5:
            top5_hits += 1

        # Stats by grade
        grade = race.grade or "other"
        if grade not in grade_stats:
            grade_stats[grade] = {"total": 0, "top1": 0, "top3": 0}
        grade_stats[grade]["total"] += 1
        if pred_top1 == actual_top1:
            grade_stats[grade]["top1"] += 1
        if pred_top1 in actual_top3:
            grade_stats[grade]["top3"] += 1

        # Stats by track type
        track = race.track_type
        if track not in track_stats:
            track_stats[track] = {"total": 0, "top1": 0, "top3": 0}
        track_stats[track]["total"] += 1
        if pred_top1 == actual_top1:
            track_stats[track]["top1"] += 1
        if pred_top1 in actual_top3:
            track_stats[track]["top3"] += 1

    # Calculate rates
    if total_races > 0:
        accuracy = {
            "top1": round(top1_hits / total_races, 2),
            "top3": round(top3_hits / total_races, 2),
            "top5": round(top5_hits / total_races, 2),
        }
    else:
        accuracy = {"top1": 0.0, "top3": 0.0, "top5": 0.0}

    by_grade = {}
    for grade, stats in grade_stats.items():
        if stats["total"] > 0:
            by_grade[grade] = {
                "top1": round(stats["top1"] / stats["total"], 2),
                "top3": round(stats["top3"] / stats["total"], 2),
            }

    by_track = {}
    for track, stats in track_stats.items():
        if stats["total"] > 0:
            by_track[track] = {
                "top1": round(stats["top1"] / stats["total"], 2),
                "top3": round(stats["top3"] / stats["total"], 2),
            }

    return {
        "period": period,
        "total_races": total_races,
        "accuracy": accuracy,
        "by_grade": by_grade,
        "by_track": by_track,
    }


@router.get("/scrape")
async def get_scrape_status(
    db: Session = Depends(get_db),
):
    """Get scraping status and data counts"""
    from app.models.horse import Horse
    from app.models.jockey import Jockey
    from datetime import date

    # Get counts
    total_races = db.execute(select(func.count(Race.race_id))).scalar() or 0
    total_horses = db.execute(select(func.count(Horse.horse_id))).scalar() or 0
    total_jockeys = db.execute(select(func.count(Jockey.jockey_id))).scalar() or 0
    total_entries = db.execute(select(func.count(Entry.id))).scalar() or 0
    total_predictions = db.execute(select(func.count(Prediction.id))).scalar() or 0

    # Get today's races count
    today = date.today()
    today_races = db.execute(
        select(func.count(Race.race_id)).where(Race.date == today)
    ).scalar() or 0

    # Get last update time (most recent race update)
    last_updated_result = db.execute(
        select(Race.updated_at).order_by(Race.updated_at.desc()).limit(1)
    ).scalar()

    last_updated = last_updated_result.isoformat() if last_updated_result else None

    # Get date range
    oldest_race = db.execute(
        select(Race.date).order_by(Race.date.asc()).limit(1)
    ).scalar()
    newest_race = db.execute(
        select(Race.date).order_by(Race.date.desc()).limit(1)
    ).scalar()

    return {
        "status": "ready",
        "last_updated": last_updated,
        "counts": {
            "total_races": total_races,
            "total_horses": total_horses,
            "total_jockeys": total_jockeys,
            "total_entries": total_entries,
            "total_predictions": total_predictions,
            "today_races": today_races,
        },
        "date_range": {
            "oldest": oldest_race.isoformat() if oldest_race else None,
            "newest": newest_race.isoformat() if newest_race else None,
        },
    }
