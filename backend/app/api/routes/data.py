from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.logging_config import get_logger
from app.services.scraper import (
    HorseScraper,
    JockeyScraper,
    TrainerScraper,
    TrainingScraper,
    OddsScraper,
)
from app.services import training_service, scraper_service

logger = get_logger(__name__)
router = APIRouter()


@router.get("/horse/{horse_id}")
async def get_horse_data(horse_id: str):
    """Get horse detail data including course aptitude"""
    scraper = HorseScraper()
    try:
        data = scraper.scrape(horse_id)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/horse/{horse_id}/past-results")
async def get_horse_past_results(horse_id: str):
    """Get horse's past race results"""
    scraper = HorseScraper()
    try:
        data = scraper.scrape_past_results(horse_id)
        return {"status": "success", "count": len(data), "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jockey/{jockey_id}")
async def get_jockey_data(jockey_id: str):
    """Get jockey detail data including win rate"""
    scraper = JockeyScraper()
    try:
        data = scraper.scrape(jockey_id)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trainer/{trainer_id}")
async def get_trainer_data(trainer_id: str):
    """Get trainer detail data"""
    scraper = TrainerScraper()
    try:
        data = scraper.scrape(trainer_id)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training/{race_id}")
async def get_training_data(
    race_id: str,
    save_to_db: bool = Query(False, description="Save to database"),
    db: Session = Depends(get_db),
):
    """Get training data for a race"""
    try:
        if save_to_db:
            # Scrape and save to database
            trainings = training_service.scrape_and_save_training(db, race_id)
            return {
                "status": "success",
                "saved": True,
                "count": len(trainings),
                "data": [
                    {
                        "id": t.id,
                        "race_id": t.race_id,
                        "horse_id": t.horse_id,
                        "horse_number": t.horse_number,
                        "training_course": t.training_course,
                        "training_time": t.training_time,
                        "lap_times": t.lap_times,
                        "training_rank": t.training_rank,
                    }
                    for t in trainings
                ],
            }
        else:
            # Just scrape without saving
            scraper = TrainingScraper()
            data = scraper.scrape(race_id)
            return {"status": "success", "saved": False, "count": len(data), "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/training/{race_id}/db")
async def get_training_from_db(
    race_id: str,
    db: Session = Depends(get_db),
):
    """Get training data from database"""
    trainings = training_service.get_training_by_race(db, race_id)
    return {
        "status": "success",
        "count": len(trainings),
        "data": [
            {
                "id": t.id,
                "race_id": t.race_id,
                "horse_id": t.horse_id,
                "horse_number": t.horse_number,
                "training_course": t.training_course,
                "training_time": t.training_time,
                "lap_times": t.lap_times,
                "training_rank": t.training_rank,
                "created_at": t.created_at.isoformat(),
            }
            for t in trainings
        ],
    }


@router.post("/training/{race_id}/scrape")
async def scrape_and_save_training(
    race_id: str,
    db: Session = Depends(get_db),
):
    """Scrape and save training data for a race"""
    try:
        trainings = training_service.scrape_and_save_training(db, race_id)
        return {
            "status": "success",
            "message": f"Saved {len(trainings)} training records",
            "count": len(trainings),
            "data": [
                {
                    "id": t.id,
                    "horse_id": t.horse_id,
                    "horse_number": t.horse_number,
                    "training_course": t.training_course,
                    "training_time": t.training_time,
                    "training_rank": t.training_rank,
                }
                for t in trainings
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/odds/{race_id}")
async def get_odds_data(
    race_id: str,
    all_types: bool = Query(False, description="Get all odds types"),
):
    """Get odds data for a race"""
    scraper = OddsScraper()
    try:
        if all_types:
            data = scraper.scrape_all(race_id)
        else:
            data = scraper.scrape(race_id)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 一括スクレイピングAPI ====================


@router.post("/scrape/races")
async def scrape_races(
    target_date: str = Query(..., description="Target date (YYYY-MM-DD)"),
    skip_existing: bool = Query(True, description="Skip existing races"),
    force: bool = Query(False, description="Force overwrite existing races (overrides skip_existing)"),
    db: Session = Depends(get_db),
):
    """
    指定日のレース情報を一括スクレイピング

    netkeibaから指定日のレース一覧を取得し、各レースの詳細情報と
    出走馬・騎手情報をDBに保存します。

    - skip_existing=True (default): 既存レースをスキップ
    - force=True: 既存レースを上書き更新（当日のオッズ更新などに使用）
    """
    try:
        parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # force=Trueの場合はskip_existingを無視
    actual_skip = False if force else skip_existing
    logger.info(f"Starting race scraping for {target_date} (force={force}, skip_existing={actual_skip})")

    try:
        result = scraper_service.scrape_races_for_date(
            db, parsed_date, skip_existing=actual_skip
        )
        logger.info(
            f"Race scraping completed: {result.success_count} saved, "
            f"{result.skipped_count} skipped, {result.error_count} errors"
        )
        return {
            "status": "success",
            "message": f"Scraped races for {target_date}",
            "result": result.to_dict(),
        }
    except Exception as e:
        logger.error(f"Race scraping failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scrape/results")
async def scrape_results(
    target_date: str = Query(..., description="Target date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """
    指定日のレース結果を一括スクレイピング

    既にDBに登録されているレースの結果（着順、タイム等）を取得して更新します。
    レース終了後に実行してください。
    """
    try:
        parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    logger.info(f"Starting result scraping for {target_date}")

    try:
        result = scraper_service.scrape_race_results(db, parsed_date)
        logger.info(
            f"Result scraping completed: {result.success_count} updated, "
            f"{result.error_count} errors"
        )
        return {
            "status": "success",
            "message": f"Scraped results for {target_date}",
            "result": result.to_dict(),
        }
    except Exception as e:
        logger.error(f"Result scraping failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scrape/training")
async def scrape_training_bulk(
    target_date: str = Query(..., description="Target date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """
    指定日の全レースの調教データを一括スクレイピング

    既にDBに登録されているレースの調教データを取得して保存します。
    """
    try:
        parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    logger.info(f"Starting training scraping for {target_date}")

    try:
        result = scraper_service.scrape_training_for_date(db, parsed_date)
        logger.info(
            f"Training scraping completed: {result.success_count} races, "
            f"{result.error_count} errors"
        )
        return {
            "status": "success",
            "message": f"Scraped training data for {target_date}",
            "result": result.to_dict(),
        }
    except Exception as e:
        logger.error(f"Training scraping failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
