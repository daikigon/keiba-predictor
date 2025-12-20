from datetime import date
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.race import Race, Entry
from app.models.horse import Horse
from app.models.jockey import Jockey
from app.services.scraper.jockey import JockeyScraper


def get_races_by_date(
    db: Session,
    target_date: Optional[date] = None,
    course: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[Race]]:
    """Get races with filters and pagination"""
    query = select(Race)

    if target_date:
        query = query.where(Race.date == target_date)
    if course:
        query = query.where(Race.course == course)

    # Get total count
    count_query = select(Race)
    if target_date:
        count_query = count_query.where(Race.date == target_date)
    if course:
        count_query = count_query.where(Race.course == course)
    total = len(db.execute(count_query).scalars().all())

    # Get paginated results
    query = query.order_by(Race.date.desc(), Race.race_number).offset(offset).limit(limit)
    races = db.execute(query).scalars().all()

    return total, list(races)


def get_race_by_id(db: Session, race_id: str) -> Optional[Race]:
    """Get a race by its ID with entries"""
    return db.get(Race, race_id)


def save_race(db: Session, race_data: dict) -> Race:
    """Save or update a race"""
    race_id = race_data["race_id"]

    existing = db.get(Race, race_id)
    if existing:
        # Update existing race
        for key, value in race_data.items():
            if key != "entries" and hasattr(existing, key):
                setattr(existing, key, value)
        race = existing
    else:
        # Create new race
        race = Race(
            race_id=race_id,
            date=race_data.get("date"),
            course=race_data.get("course", ""),
            race_number=race_data.get("race_number", 0),
            race_name=race_data.get("race_name"),
            distance=race_data.get("distance", 0),
            track_type=race_data.get("track_type", ""),
            weather=race_data.get("weather"),
            condition=race_data.get("condition"),
            grade=race_data.get("grade"),
        )
        db.add(race)

    db.commit()
    db.refresh(race)
    return race


def save_race_with_entries(db: Session, race_data: dict) -> Race:
    """Save race with all entries (horses, jockeys)"""
    entries_data = race_data.pop("entries", [])

    # Save race
    race = save_race(db, race_data)

    # Save entries
    for entry_data in entries_data:
        # Save horse if exists
        horse_id = entry_data.get("horse_id")
        if horse_id:
            _ensure_horse(db, horse_id, entry_data)

        # Save jockey if exists
        jockey_id = entry_data.get("jockey_id")
        if jockey_id:
            _ensure_jockey(db, jockey_id, entry_data)

        # Save entry
        _save_entry(db, race.race_id, entry_data)

    db.commit()
    db.refresh(race)
    return race


def _ensure_horse(db: Session, horse_id: str, entry_data: dict) -> Horse:
    """Ensure horse exists in database"""
    horse = db.get(Horse, horse_id)
    if not horse:
        horse = Horse(
            horse_id=horse_id,
            name=entry_data.get("horse_name", "Unknown"),
            sex=entry_data.get("sex", "不明"),
            birth_year=2024 - entry_data.get("age", 3),
        )
        db.add(horse)
        db.flush()
    return horse


def _ensure_jockey(db: Session, jockey_id: str, entry_data: dict) -> Jockey:
    """Ensure jockey exists in database"""
    jockey = db.get(Jockey, jockey_id)
    if not jockey:
        # Try to fetch full name from jockey detail page
        jockey_name = entry_data.get("jockey_name", "Unknown")
        try:
            scraper = JockeyScraper()
            jockey_info = scraper.scrape(jockey_id)
            if jockey_info.get("name"):
                jockey_name = jockey_info["name"]
        except Exception:
            pass  # Fall back to entry_data name

        jockey = Jockey(
            jockey_id=jockey_id,
            name=jockey_name,
        )
        db.add(jockey)
        db.flush()
    return jockey


def _save_entry(db: Session, race_id: str, entry_data: dict) -> Entry:
    """Save or update an entry"""
    horse_number = entry_data.get("horse_number")

    # Check if entry exists
    stmt = select(Entry).where(
        Entry.race_id == race_id,
        Entry.horse_number == horse_number
    )
    existing = db.execute(stmt).scalar_one_or_none()

    if existing:
        # Update existing entry
        for key in ["frame_number", "weight", "horse_weight", "weight_diff",
                    "odds", "popularity", "result", "finish_time", "margin",
                    "corner_position", "last_3f"]:
            if key in entry_data and entry_data[key] is not None:
                setattr(existing, key, entry_data[key])
        return existing

    # Create new entry
    entry = Entry(
        race_id=race_id,
        horse_id=entry_data.get("horse_id"),
        jockey_id=entry_data.get("jockey_id"),
        frame_number=entry_data.get("frame_number"),
        horse_number=horse_number,
        weight=entry_data.get("weight"),
        horse_weight=entry_data.get("horse_weight"),
        weight_diff=entry_data.get("weight_diff"),
        odds=entry_data.get("odds"),
        popularity=entry_data.get("popularity"),
        result=entry_data.get("result"),
        finish_time=entry_data.get("finish_time"),
        margin=entry_data.get("margin"),
        corner_position=entry_data.get("corner_position"),
        last_3f=entry_data.get("last_3f"),
    )
    db.add(entry)
    db.flush()
    return entry
