from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.scraper import RaceListScraper, RaceDetailScraper, RaceCardListScraper, RaceCardScraper
from app.services import race_service

router = APIRouter()


@router.get("")
async def get_races(
    target_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    course: Optional[str] = Query(None, description="Course name"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get race list"""
    parsed_date = None
    if target_date:
        try:
            parsed_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    total, races = race_service.get_races_by_date(
        db, target_date=parsed_date, course=course, limit=limit, offset=offset
    )

    return {
        "total": total,
        "races": [
            {
                "race_id": r.race_id,
                "date": r.date.isoformat(),
                "course": r.course,
                "race_number": r.race_number,
                "race_name": r.race_name,
                "distance": r.distance,
                "track_type": r.track_type,
                "grade": r.grade,
            }
            for r in races
        ],
    }


@router.get("/{race_id}")
async def get_race(
    race_id: str,
    db: Session = Depends(get_db),
):
    """Get race detail"""
    race = race_service.get_race_by_id(db, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")

    return {
        "race_id": race.race_id,
        "date": race.date.isoformat(),
        "course": race.course,
        "race_number": race.race_number,
        "race_name": race.race_name,
        "distance": race.distance,
        "track_type": race.track_type,
        "weather": race.weather,
        "condition": race.condition,
        "grade": race.grade,
        "entries": [
            {
                "horse_number": e.horse_number,
                "frame_number": e.frame_number,
                "horse_id": e.horse_id,
                "horse_name": e.horse.name if e.horse else None,
                "jockey_id": e.jockey_id,
                "jockey_name": e.jockey.name if e.jockey else None,
                "weight": e.weight,
                "odds": e.odds,
                "popularity": e.popularity,
                "result": e.result,
                "finish_time": e.finish_time,
            }
            for e in sorted(race.entries, key=lambda x: x.horse_number)
        ],
    }


@router.post("/scrape")
async def scrape_races(
    target_date: str = Query(..., description="Date in YYYY-MM-DD format"),
    save_to_db: bool = Query(False, description="Save to database"),
    db: Session = Depends(get_db),
):
    """Scrape races for a given date"""
    try:
        parsed_date = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    scraper = RaceListScraper()
    races = scraper.scrape(parsed_date)

    saved_count = 0
    if save_to_db:
        for race_data in races:
            race_service.save_race(db, race_data)
            saved_count += 1

    return {
        "status": "success",
        "message": f"Scraped {len(races)} races" + (f", saved {saved_count}" if save_to_db else ""),
        "races_count": len(races),
        "saved_count": saved_count,
        "races": races,
    }


@router.post("/scrape/{race_id}")
async def scrape_race_detail(
    race_id: str,
    save_to_db: bool = Query(True, description="Save to database"),
    skip_existing: bool = Query(True, description="Skip if race already has entries"),
    db: Session = Depends(get_db),
):
    """Scrape race detail and save to database"""
    # Check if race already exists with entries
    if skip_existing:
        existing_race = race_service.get_race_by_id(db, race_id)
        if existing_race and len(existing_race.entries) > 0:
            return {
                "status": "skipped",
                "saved": False,
                "skipped": True,
                "reason": "Race already has entries",
                "race": {
                    "race_id": race_id,
                    "race_name": existing_race.race_name,
                    "entries_count": len(existing_race.entries),
                },
            }

    scraper = RaceDetailScraper()
    race_detail = scraper.scrape(race_id)

    if save_to_db:
        race_service.save_race_with_entries(db, race_detail.copy())

    return {
        "status": "success",
        "saved": save_to_db,
        "skipped": False,
        "race": race_detail,
    }


# === Race Card (出馬表) Endpoints for Today's Races ===

@router.post("/scrape-card")
async def scrape_race_cards(
    target_date: str = Query(..., description="Date in YYYY-MM-DD format"),
    save_to_db: bool = Query(True, description="Save to database"),
    db: Session = Depends(get_db),
):
    """Scrape race cards (出馬表) from race.netkeiba.com for today/upcoming races"""
    try:
        parsed_date = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    scraper = RaceCardListScraper()
    races = scraper.scrape(parsed_date)

    saved_count = 0
    if save_to_db:
        for race_data in races:
            race_service.save_race(db, race_data)
            saved_count += 1

    return {
        "status": "success",
        "message": f"Scraped {len(races)} race cards",
        "races_count": len(races),
        "saved_count": saved_count,
        "races": races,
        "source": "race.netkeiba.com",
    }


@router.post("/scrape-card/{race_id}")
async def scrape_race_card_detail(
    race_id: str,
    save_to_db: bool = Query(True, description="Save to database"),
    skip_existing: bool = Query(True, description="Skip if race already has entries"),
    db: Session = Depends(get_db),
):
    """Scrape race card detail (出馬表) from race.netkeiba.com"""
    # Check if race already exists with entries
    if skip_existing:
        existing_race = race_service.get_race_by_id(db, race_id)
        if existing_race and len(existing_race.entries) > 0:
            return {
                "status": "skipped",
                "saved": False,
                "skipped": True,
                "reason": "Race already has entries",
                "race": {
                    "race_id": race_id,
                    "race_name": existing_race.race_name,
                    "entries_count": len(existing_race.entries),
                },
                "source": "race.netkeiba.com",
            }

    scraper = RaceCardScraper()
    race_detail = scraper.scrape(race_id)

    if save_to_db:
        race_service.save_race_with_entries(db, race_detail.copy())

    return {
        "status": "success",
        "saved": save_to_db,
        "skipped": False,
        "race": race_detail,
        "source": "race.netkeiba.com",
    }
