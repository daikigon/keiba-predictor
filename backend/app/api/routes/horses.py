from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.models.horse import Horse
from app.models.jockey import Jockey
from app.models.race import Entry, Race
from app.services.scraper.horse import HorseScraper
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()

# 一括補完の進捗管理
_bulk_rescrape_status = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "current_horse": None,
    "results": None,
    "error": None,
}


@router.get("")
async def get_horses(
    search: Optional[str] = Query(None, description="Search by name"),
    sex: Optional[str] = Query(None, description="Filter by sex (牡/牝/セ)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get horse list with search and filter"""
    query = db.query(Horse)

    if search:
        query = query.filter(Horse.name.contains(search))
    if sex:
        query = query.filter(Horse.sex == sex)

    total = query.count()
    horses = query.order_by(Horse.name).offset(offset).limit(limit).all()

    return {
        "total": total,
        "horses": [
            {
                "horse_id": h.horse_id,
                "name": h.name,
                "sex": h.sex,
                "birth_year": h.birth_year,
                "father": h.father,
                "mother": h.mother,
                "trainer": h.trainer,
                "entries_count": len(h.entries) if h.entries else 0,
            }
            for h in horses
        ],
    }


@router.get("/stats")
async def get_horse_stats(
    db: Session = Depends(get_db),
):
    """Get horse statistics"""
    total = db.query(Horse).count()

    # Count by sex
    sex_counts = (
        db.query(Horse.sex, func.count(Horse.horse_id))
        .group_by(Horse.sex)
        .all()
    )

    # Count by birth year (recent 10 years)
    birth_year_counts = (
        db.query(Horse.birth_year, func.count(Horse.horse_id))
        .group_by(Horse.birth_year)
        .order_by(Horse.birth_year.desc())
        .limit(10)
        .all()
    )

    return {
        "total": total,
        "by_sex": {sex: count for sex, count in sex_counts},
        "by_birth_year": {year: count for year, count in birth_year_counts},
    }


@router.get("/{horse_id}")
async def get_horse(
    horse_id: str,
    db: Session = Depends(get_db),
):
    """Get horse detail with race history"""
    horse = db.query(Horse).filter(Horse.horse_id == horse_id).first()
    if not horse:
        raise HTTPException(status_code=404, detail="Horse not found")

    # Get race history from entries
    entries = (
        db.query(Entry)
        .filter(Entry.horse_id == horse_id)
        .order_by(Entry.race_id.desc())
        .limit(20)
        .all()
    )

    race_history = []
    for e in entries:
        race = e.race
        if race:
            race_history.append({
                "race_id": race.race_id,
                "date": race.date.isoformat() if race.date else None,
                "venue_detail": race.venue_detail,
                "weather": race.weather,
                "race_number": race.race_number,
                "race_name": race.race_name,
                "num_horses": race.num_horses,
                "course": race.course,
                "distance": race.distance,
                "track_type": race.track_type,
                "condition": race.condition,
                "frame_number": e.frame_number,
                "horse_number": e.horse_number,
                "odds": e.odds,
                "popularity": e.popularity,
                "result": e.result,
                "jockey_name": e.jockey.name if e.jockey else None,
                "weight": e.weight,
                "finish_time": e.finish_time,
                "margin": e.margin,
                "corner_position": e.corner_position,
                "pace": e.pace,
                "last_3f": e.last_3f,
                "horse_weight": e.horse_weight,
                "weight_diff": e.weight_diff,
                "prize_money": e.prize_money,
                "winner_or_second": e.winner_or_second,
            })

    return {
        "horse_id": horse.horse_id,
        "name": horse.name,
        "sex": horse.sex,
        "birth_year": horse.birth_year,
        "father": horse.father,
        "mother": horse.mother,
        "mother_father": horse.mother_father,
        "trainer": horse.trainer,
        "owner": horse.owner,
        "race_history": race_history,
    }


def _parse_race_date(date_str: str) -> datetime:
    """Parse date string like '2026/01/05' to date object"""
    try:
        return datetime.strptime(date_str, "%Y/%m/%d").date()
    except ValueError:
        return datetime.now().date()


def _get_course_from_race_id(race_id: str) -> str:
    """Extract course name from race_id"""
    course_codes = {
        "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
        "05": "東京", "06": "中山", "07": "中京", "08": "京都",
        "09": "阪神", "10": "小倉",
    }
    if len(race_id) >= 6:
        course_code = race_id[4:6]
        return course_codes.get(course_code, "不明")
    return "不明"


@router.post("/{horse_id}/rescrape")
async def rescrape_horse_data(
    horse_id: str,
    db: Session = Depends(get_db),
):
    """
    Rescrape horse data from netkeiba horse page and update database.
    Creates new Race/Entry records if they don't exist.
    """
    # Check if horse exists
    horse = db.query(Horse).filter(Horse.horse_id == horse_id).first()
    if not horse:
        raise HTTPException(status_code=404, detail="Horse not found")

    try:
        # Scrape horse page
        scraper = HorseScraper()

        # Update horse basic info
        horse_info = scraper.scrape(horse_id)
        if horse_info:
            if horse_info.get("father"):
                horse.father = horse_info["father"]
            if horse_info.get("mother"):
                horse.mother = horse_info["mother"]
            if horse_info.get("mother_father"):
                horse.mother_father = horse_info["mother_father"]
            if horse_info.get("trainer"):
                horse.trainer = horse_info["trainer"]
            if horse_info.get("owner"):
                horse.owner = horse_info["owner"]
            if horse_info.get("birth_year"):
                horse.birth_year = horse_info["birth_year"]
            if horse_info.get("sex"):
                horse.sex = horse_info["sex"]

        # Scrape past results from horse page
        past_results = scraper.scrape_past_results(horse_id)

        updated_entries = 0
        created_entries = 0
        updated_races = 0
        created_races = 0

        for result in past_results:
            race_id = result.get("race_id")
            if not race_id:
                continue

            # Get or create Race record
            race = db.query(Race).filter(Race.race_id == race_id).first()
            if race:
                # Update existing race
                if result.get("venue_detail") and not race.venue_detail:
                    race.venue_detail = result["venue_detail"]
                if result.get("weather") and not race.weather:
                    race.weather = result["weather"]
                if result.get("num_horses") and not race.num_horses:
                    race.num_horses = result["num_horses"]
                if result.get("condition") and not race.condition:
                    race.condition = result["condition"]
                updated_races += 1
            else:
                # Create new race record
                race = Race(
                    race_id=race_id,
                    date=_parse_race_date(result.get("date", "")),
                    course=_get_course_from_race_id(race_id),
                    race_number=result.get("race_number", 0),
                    race_name=result.get("race_name"),
                    distance=result.get("distance", 0),
                    track_type=result.get("track_type", "不明"),
                    weather=result.get("weather"),
                    condition=result.get("condition"),
                    num_horses=result.get("num_horses"),
                    venue_detail=result.get("venue_detail"),
                )
                db.add(race)
                created_races += 1

            # Get or create Jockey record if jockey_id exists
            jockey_id = result.get("jockey_id")
            if jockey_id:
                jockey = db.query(Jockey).filter(Jockey.jockey_id == jockey_id).first()
                if not jockey:
                    jockey = Jockey(
                        jockey_id=jockey_id,
                        name=result.get("jockey_name", "不明"),
                    )
                    db.add(jockey)

            # Get or create Entry record
            entry = (
                db.query(Entry)
                .filter(Entry.race_id == race_id, Entry.horse_id == horse_id)
                .first()
            )
            if entry:
                # Update existing entry (only if fields are empty/null)
                if result.get("frame_number") and not entry.frame_number:
                    entry.frame_number = result["frame_number"]
                if result.get("odds") and not entry.odds:
                    entry.odds = result["odds"]
                if result.get("popularity") and not entry.popularity:
                    entry.popularity = result["popularity"]
                if result.get("result") and not entry.result:
                    entry.result = result["result"]
                if result.get("weight") and not entry.weight:
                    entry.weight = result["weight"]
                if result.get("finish_time") and not entry.finish_time:
                    entry.finish_time = result["finish_time"]
                if result.get("margin") and not entry.margin:
                    entry.margin = result["margin"]
                if result.get("corner_position") and not entry.corner_position:
                    entry.corner_position = result["corner_position"]
                if result.get("pace") and not entry.pace:
                    entry.pace = result["pace"]
                if result.get("last_3f") and not entry.last_3f:
                    entry.last_3f = result["last_3f"]
                if result.get("horse_weight") and not entry.horse_weight:
                    entry.horse_weight = result["horse_weight"]
                if result.get("weight_diff") is not None and entry.weight_diff is None:
                    entry.weight_diff = result["weight_diff"]
                if result.get("prize_money") and not entry.prize_money:
                    entry.prize_money = result["prize_money"]
                if result.get("winner_or_second") and not entry.winner_or_second:
                    entry.winner_or_second = result["winner_or_second"]
                if jockey_id and not entry.jockey_id:
                    entry.jockey_id = jockey_id
                updated_entries += 1
            else:
                # Create new entry record
                entry = Entry(
                    race_id=race_id,
                    horse_id=horse_id,
                    jockey_id=jockey_id,
                    frame_number=result.get("frame_number"),
                    horse_number=result.get("horse_number", 0),
                    weight=result.get("weight"),
                    horse_weight=result.get("horse_weight"),
                    weight_diff=result.get("weight_diff"),
                    odds=result.get("odds"),
                    popularity=result.get("popularity"),
                    result=result.get("result"),
                    finish_time=result.get("finish_time"),
                    margin=result.get("margin"),
                    corner_position=result.get("corner_position"),
                    last_3f=result.get("last_3f"),
                    pace=result.get("pace"),
                    prize_money=result.get("prize_money"),
                    winner_or_second=result.get("winner_or_second"),
                )
                db.add(entry)
                created_entries += 1

        db.commit()

        return {
            "success": True,
            "horse_id": horse_id,
            "horse_name": horse.name,
            "scraped_races": len(past_results),
            "updated_entries": updated_entries,
            "created_entries": created_entries,
            "updated_races": updated_races,
            "created_races": created_races,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


# ================== 一括補完機能 ==================

def _run_bulk_rescrape():
    """バックグラウンドで全馬の一括補完を実行"""
    global _bulk_rescrape_status

    db = SessionLocal()
    try:
        _bulk_rescrape_status["is_running"] = True
        _bulk_rescrape_status["progress"] = 0
        _bulk_rescrape_status["error"] = None
        _bulk_rescrape_status["results"] = None

        # 全馬を取得
        horses = db.query(Horse).all()
        _bulk_rescrape_status["total"] = len(horses)

        scraper = HorseScraper()
        total_scraped_races = 0
        total_created_entries = 0
        total_created_races = 0
        total_updated_entries = 0
        total_updated_races = 0
        processed_horses = 0
        failed_horses = []

        for i, horse in enumerate(horses):
            _bulk_rescrape_status["progress"] = i + 1
            _bulk_rescrape_status["current_horse"] = horse.name

            try:
                # 馬情報を更新
                horse_info = scraper.scrape(horse.horse_id)
                if horse_info:
                    if horse_info.get("father"):
                        horse.father = horse_info["father"]
                    if horse_info.get("mother"):
                        horse.mother = horse_info["mother"]
                    if horse_info.get("mother_father"):
                        horse.mother_father = horse_info["mother_father"]
                    if horse_info.get("trainer"):
                        horse.trainer = horse_info["trainer"]
                    if horse_info.get("owner"):
                        horse.owner = horse_info["owner"]
                    if horse_info.get("birth_year"):
                        horse.birth_year = horse_info["birth_year"]
                    if horse_info.get("sex"):
                        horse.sex = horse_info["sex"]

                # 過去成績を取得
                past_results = scraper.scrape_past_results(horse.horse_id)
                total_scraped_races += len(past_results)

                for result in past_results:
                    race_id = result.get("race_id")
                    if not race_id:
                        continue

                    # Race レコードの処理
                    race = db.query(Race).filter(Race.race_id == race_id).first()
                    if race:
                        if result.get("venue_detail") and not race.venue_detail:
                            race.venue_detail = result["venue_detail"]
                        if result.get("weather") and not race.weather:
                            race.weather = result["weather"]
                        if result.get("num_horses") and not race.num_horses:
                            race.num_horses = result["num_horses"]
                        if result.get("condition") and not race.condition:
                            race.condition = result["condition"]
                        total_updated_races += 1
                    else:
                        race = Race(
                            race_id=race_id,
                            date=_parse_race_date(result.get("date", "")),
                            course=_get_course_from_race_id(race_id),
                            race_number=result.get("race_number", 0),
                            race_name=result.get("race_name"),
                            distance=result.get("distance", 0),
                            track_type=result.get("track_type", "不明"),
                            weather=result.get("weather"),
                            condition=result.get("condition"),
                            num_horses=result.get("num_horses"),
                            venue_detail=result.get("venue_detail"),
                        )
                        db.add(race)
                        total_created_races += 1

                    # Jockey レコードの処理
                    jockey_id = result.get("jockey_id")
                    if jockey_id:
                        jockey = db.query(Jockey).filter(Jockey.jockey_id == jockey_id).first()
                        if not jockey:
                            jockey = Jockey(
                                jockey_id=jockey_id,
                                name=result.get("jockey_name", "不明"),
                            )
                            db.add(jockey)

                    # Entry レコードの処理
                    entry = (
                        db.query(Entry)
                        .filter(Entry.race_id == race_id, Entry.horse_id == horse.horse_id)
                        .first()
                    )
                    if entry:
                        if result.get("frame_number") and not entry.frame_number:
                            entry.frame_number = result["frame_number"]
                        if result.get("odds") and not entry.odds:
                            entry.odds = result["odds"]
                        if result.get("popularity") and not entry.popularity:
                            entry.popularity = result["popularity"]
                        if result.get("result") and not entry.result:
                            entry.result = result["result"]
                        if result.get("weight") and not entry.weight:
                            entry.weight = result["weight"]
                        if result.get("finish_time") and not entry.finish_time:
                            entry.finish_time = result["finish_time"]
                        if result.get("margin") and not entry.margin:
                            entry.margin = result["margin"]
                        if result.get("corner_position") and not entry.corner_position:
                            entry.corner_position = result["corner_position"]
                        if result.get("pace") and not entry.pace:
                            entry.pace = result["pace"]
                        if result.get("last_3f") and not entry.last_3f:
                            entry.last_3f = result["last_3f"]
                        if result.get("horse_weight") and not entry.horse_weight:
                            entry.horse_weight = result["horse_weight"]
                        if result.get("weight_diff") is not None and entry.weight_diff is None:
                            entry.weight_diff = result["weight_diff"]
                        if result.get("prize_money") and not entry.prize_money:
                            entry.prize_money = result["prize_money"]
                        if result.get("winner_or_second") and not entry.winner_or_second:
                            entry.winner_or_second = result["winner_or_second"]
                        if jockey_id and not entry.jockey_id:
                            entry.jockey_id = jockey_id
                        total_updated_entries += 1
                    else:
                        entry = Entry(
                            race_id=race_id,
                            horse_id=horse.horse_id,
                            jockey_id=jockey_id,
                            frame_number=result.get("frame_number"),
                            horse_number=result.get("horse_number", 0),
                            weight=result.get("weight"),
                            horse_weight=result.get("horse_weight"),
                            weight_diff=result.get("weight_diff"),
                            odds=result.get("odds"),
                            popularity=result.get("popularity"),
                            result=result.get("result"),
                            finish_time=result.get("finish_time"),
                            margin=result.get("margin"),
                            corner_position=result.get("corner_position"),
                            last_3f=result.get("last_3f"),
                            pace=result.get("pace"),
                            prize_money=result.get("prize_money"),
                            winner_or_second=result.get("winner_or_second"),
                        )
                        db.add(entry)
                        total_created_entries += 1

                # 10頭ごとにコミット
                if (i + 1) % 10 == 0:
                    db.commit()

                processed_horses += 1

            except Exception as e:
                logger.error(f"Failed to rescrape horse {horse.horse_id}: {e}")
                failed_horses.append({"horse_id": horse.horse_id, "name": horse.name, "error": str(e)})
                continue

        # 最終コミット
        db.commit()

        _bulk_rescrape_status["results"] = {
            "processed_horses": processed_horses,
            "failed_horses": len(failed_horses),
            "total_scraped_races": total_scraped_races,
            "created_entries": total_created_entries,
            "updated_entries": total_updated_entries,
            "created_races": total_created_races,
            "updated_races": total_updated_races,
            "failures": failed_horses[:10],  # 最初の10件のエラーのみ
        }

    except Exception as e:
        logger.error(f"Bulk rescrape failed: {e}")
        _bulk_rescrape_status["error"] = str(e)
    finally:
        _bulk_rescrape_status["is_running"] = False
        _bulk_rescrape_status["current_horse"] = None
        db.close()


@router.post("/bulk-rescrape")
async def start_bulk_rescrape(background_tasks: BackgroundTasks):
    """
    全競走馬の一括データ補完を開始

    バックグラウンドで実行され、進捗は GET /api/v1/horses/bulk-rescrape/status で確認できます。
    """
    global _bulk_rescrape_status

    if _bulk_rescrape_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="一括補完は既に実行中です"
        )

    background_tasks.add_task(_run_bulk_rescrape)

    return {
        "status": "success",
        "message": "一括補完を開始しました",
    }


@router.get("/bulk-rescrape/status")
async def get_bulk_rescrape_status():
    """
    一括補完の進捗状況を取得
    """
    return {
        "status": "success",
        "bulk_rescrape": _bulk_rescrape_status,
    }
