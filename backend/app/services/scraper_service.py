"""
一括スクレイピングサービス

APIから呼び出し可能なスクレイピング機能を提供
"""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models import Race, Entry, Horse, Jockey
from app.services.scraper import (
    RaceListScraper,
    RaceDetailScraper,
    HorseScraper,
    TrainingScraper,
)
from app.services import training_service

logger = get_logger(__name__)


class ScrapeResult:
    """スクレイピング結果"""

    def __init__(self):
        self.success_count = 0
        self.error_count = 0
        self.skipped_count = 0
        self.errors: list[dict] = []
        self.saved_items: list[str] = []

    def to_dict(self) -> dict:
        return {
            "success_count": self.success_count,
            "error_count": self.error_count,
            "skipped_count": self.skipped_count,
            "errors": self.errors,
            "saved_items": self.saved_items,
        }


def scrape_races_for_date(
    db: Session,
    target_date: date,
    skip_existing: bool = True,
) -> ScrapeResult:
    """
    指定日のレース情報をスクレイピングしてDBに保存

    Args:
        db: データベースセッション
        target_date: 対象日
        skip_existing: 既存レースをスキップするか

    Returns:
        スクレイピング結果
    """
    result = ScrapeResult()
    logger.info(f"Scraping races for {target_date}")

    list_scraper = RaceListScraper()
    detail_scraper = RaceDetailScraper()
    horse_scraper = HorseScraper()

    try:
        races = list_scraper.scrape(target_date)
    except Exception as e:
        logger.error(f"Failed to get race list: {e}")
        result.errors.append({"type": "race_list", "error": str(e)})
        result.error_count += 1
        return result

    if not races:
        logger.info("No races found")
        return result

    logger.info(f"Found {len(races)} races")

    for race_info in races:
        race_id = race_info["race_id"]

        try:
            # 既存チェック
            if skip_existing:
                existing = db.query(Race).filter(Race.race_id == race_id).first()
                if existing:
                    logger.debug(f"Race {race_id} already exists, skipping")
                    result.skipped_count += 1
                    continue

            # レース詳細取得
            detail = detail_scraper.scrape(race_id)

            # Raceレコード作成
            race = Race(
                race_id=race_id,
                date=target_date,
                course=detail.get("course", ""),
                race_number=detail.get("race_number", 0),
                race_name=detail.get("race_name"),
                distance=detail.get("distance", 0),
                track_type=detail.get("track_type", ""),
                weather=detail.get("weather"),
                condition=detail.get("condition"),
                grade=detail.get("grade"),
            )
            db.add(race)

            # エントリー処理
            for entry_data in detail.get("entries", []):
                _process_entry(db, race_id, entry_data, horse_scraper)

            db.commit()
            result.success_count += 1
            result.saved_items.append(race_id)
            logger.info(f"Saved race {race_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Error processing race {race_id}: {e}")
            result.errors.append({"race_id": race_id, "error": str(e)})
            result.error_count += 1

    return result


def _process_entry(
    db: Session,
    race_id: str,
    entry_data: dict,
    horse_scraper: HorseScraper,
) -> None:
    """エントリーを処理してDBに保存"""
    horse_id = entry_data.get("horse_id")
    jockey_id = entry_data.get("jockey_id")

    # 馬の取得または作成
    if horse_id:
        horse = db.query(Horse).filter(Horse.horse_id == horse_id).first()
        if not horse:
            try:
                horse_info = horse_scraper.scrape(horse_id)
                horse = Horse(
                    horse_id=horse_id,
                    name=horse_info.get("name", entry_data.get("horse_name", "")),
                    sex=horse_info.get("sex", ""),
                    birth_year=horse_info.get("birth_year", 2020),
                    father=horse_info.get("father"),
                    mother=horse_info.get("mother"),
                    mother_father=horse_info.get("mother_father"),
                    trainer=horse_info.get("trainer"),
                    owner=horse_info.get("owner"),
                )
                db.add(horse)
            except Exception as e:
                logger.warning(f"Could not get horse info for {horse_id}: {e}")
                horse = Horse(
                    horse_id=horse_id,
                    name=entry_data.get("horse_name", "Unknown"),
                    sex="",
                    birth_year=2020,
                )
                db.add(horse)

    # 騎手の取得または作成
    if jockey_id:
        jockey = db.query(Jockey).filter(Jockey.jockey_id == jockey_id).first()
        if not jockey:
            jockey = Jockey(
                jockey_id=jockey_id,
                name=entry_data.get("jockey_name", "Unknown"),
            )
            db.add(jockey)

    # エントリー作成
    entry = Entry(
        race_id=race_id,
        horse_id=horse_id or "",
        jockey_id=jockey_id,
        frame_number=entry_data.get("frame_number"),
        horse_number=entry_data.get("horse_number", 0),
        weight=entry_data.get("weight"),
        odds=entry_data.get("odds"),
        popularity=entry_data.get("popularity"),
    )
    db.add(entry)


def scrape_race_results(
    db: Session,
    target_date: date,
) -> ScrapeResult:
    """
    指定日のレース結果をスクレイピングして更新

    Args:
        db: データベースセッション
        target_date: 対象日

    Returns:
        スクレイピング結果
    """
    result = ScrapeResult()
    logger.info(f"Scraping race results for {target_date}")

    detail_scraper = RaceDetailScraper()

    # 対象日のレースを取得
    races = db.query(Race).filter(Race.date == target_date).all()

    if not races:
        logger.info("No races found for the date")
        return result

    for race in races:
        try:
            detail = detail_scraper.scrape(race.race_id)

            # エントリーの結果を更新
            for entry_data in detail.get("entries", []):
                horse_number = entry_data.get("horse_number")
                race_result = entry_data.get("result")

                if horse_number and race_result is not None:
                    entry = (
                        db.query(Entry)
                        .filter(
                            Entry.race_id == race.race_id,
                            Entry.horse_number == horse_number,
                        )
                        .first()
                    )
                    if entry:
                        entry.result = race_result
                        entry.finish_time = entry_data.get("finish_time")
                        entry.margin = entry_data.get("margin")
                        entry.last_3f = entry_data.get("last_3f")
                        entry.horse_weight = entry_data.get("horse_weight")
                        entry.weight_diff = entry_data.get("weight_diff")

            db.commit()
            result.success_count += 1
            result.saved_items.append(race.race_id)
            logger.info(f"Updated results for race {race.race_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Error updating race {race.race_id}: {e}")
            result.errors.append({"race_id": race.race_id, "error": str(e)})
            result.error_count += 1

    return result


def scrape_training_for_date(
    db: Session,
    target_date: date,
) -> ScrapeResult:
    """
    指定日の全レースの調教データをスクレイピング

    Args:
        db: データベースセッション
        target_date: 対象日

    Returns:
        スクレイピング結果
    """
    result = ScrapeResult()
    logger.info(f"Scraping training data for {target_date}")

    # 対象日のレースを取得
    races = db.query(Race).filter(Race.date == target_date).all()

    if not races:
        logger.info("No races found for the date")
        return result

    for race in races:
        try:
            trainings = training_service.scrape_and_save_training(db, race.race_id)
            result.success_count += 1
            result.saved_items.append(f"{race.race_id}: {len(trainings)} records")
            logger.info(f"Saved {len(trainings)} training records for {race.race_id}")

        except Exception as e:
            logger.error(f"Error scraping training for {race.race_id}: {e}")
            result.errors.append({"race_id": race.race_id, "error": str(e)})
            result.error_count += 1

    return result
