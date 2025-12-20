import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.jockey import Jockey
from app.models.race import Entry
from app.services.scraper.jockey import JockeyScraper

router = APIRouter()


@router.get("")
async def get_jockeys(
    search: Optional[str] = Query(None, description="Search by name"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get jockey list with search"""
    query = db.query(Jockey)

    if search:
        query = query.filter(Jockey.name.contains(search))

    total = query.count()
    jockeys = query.order_by(Jockey.name).offset(offset).limit(limit).all()

    # Get entry counts for each jockey
    result = []
    for j in jockeys:
        entries_count = db.query(Entry).filter(Entry.jockey_id == j.jockey_id).count()

        # Calculate win stats from entries
        wins = db.query(Entry).filter(
            Entry.jockey_id == j.jockey_id,
            Entry.result == 1
        ).count()

        places = db.query(Entry).filter(
            Entry.jockey_id == j.jockey_id,
            Entry.result <= 2,
            Entry.result >= 1
        ).count()

        shows = db.query(Entry).filter(
            Entry.jockey_id == j.jockey_id,
            Entry.result <= 3,
            Entry.result >= 1
        ).count()

        result.append({
            "jockey_id": j.jockey_id,
            "name": j.name,
            "entries_count": entries_count,
            "wins": wins,
            "win_rate": round(wins / entries_count * 100, 1) if entries_count > 0 else 0,
            "place_rate": round(places / entries_count * 100, 1) if entries_count > 0 else 0,
            "show_rate": round(shows / entries_count * 100, 1) if entries_count > 0 else 0,
        })

    return {
        "total": total,
        "jockeys": result,
    }


@router.get("/stats")
async def get_jockey_stats(
    db: Session = Depends(get_db),
):
    """Get jockey statistics"""
    total = db.query(Jockey).count()

    # Top jockeys by entries
    top_by_entries = (
        db.query(Jockey.jockey_id, Jockey.name, func.count(Entry.id).label("count"))
        .join(Entry, Entry.jockey_id == Jockey.jockey_id)
        .group_by(Jockey.jockey_id, Jockey.name)
        .order_by(func.count(Entry.id).desc())
        .limit(10)
        .all()
    )

    return {
        "total": total,
        "top_by_entries": [
            {"jockey_id": j_id, "name": name, "entries_count": count}
            for j_id, name, count in top_by_entries
        ],
    }


@router.get("/{jockey_id}")
async def get_jockey(
    jockey_id: str,
    db: Session = Depends(get_db),
):
    """Get jockey detail with race history"""
    jockey = db.query(Jockey).filter(Jockey.jockey_id == jockey_id).first()
    if not jockey:
        raise HTTPException(status_code=404, detail="Jockey not found")

    # Get race history from entries
    entries = (
        db.query(Entry)
        .filter(Entry.jockey_id == jockey_id)
        .order_by(Entry.race_id.desc())
        .limit(30)
        .all()
    )

    # Calculate stats
    total_entries = db.query(Entry).filter(Entry.jockey_id == jockey_id).count()
    wins = db.query(Entry).filter(Entry.jockey_id == jockey_id, Entry.result == 1).count()
    places = db.query(Entry).filter(Entry.jockey_id == jockey_id, Entry.result <= 2, Entry.result >= 1).count()
    shows = db.query(Entry).filter(Entry.jockey_id == jockey_id, Entry.result <= 3, Entry.result >= 1).count()

    race_history = []
    for e in entries:
        race = e.race
        if race:
            race_history.append({
                "race_id": race.race_id,
                "date": race.date.isoformat() if race.date else None,
                "race_name": race.race_name,
                "course": race.course,
                "distance": race.distance,
                "track_type": race.track_type,
                "horse_number": e.horse_number,
                "horse_name": e.horse.name if e.horse else None,
                "result": e.result,
                "odds": e.odds,
                "popularity": e.popularity,
            })

    return {
        "jockey_id": jockey.jockey_id,
        "name": jockey.name,
        "stats": {
            "total_entries": total_entries,
            "wins": wins,
            "win_rate": round(wins / total_entries * 100, 1) if total_entries > 0 else 0,
            "place_rate": round(places / total_entries * 100, 1) if total_entries > 0 else 0,
            "show_rate": round(shows / total_entries * 100, 1) if total_entries > 0 else 0,
        },
        "race_history": race_history,
    }


@router.post("/refresh-names")
async def refresh_jockey_names(
    db: Session = Depends(get_db),
):
    """Refresh all jockey names from their detail pages"""
    jockeys = db.query(Jockey).all()
    scraper = JockeyScraper()

    updated = 0
    errors = 0

    for jockey in jockeys:
        try:
            jockey_info = scraper.scrape(jockey.jockey_id)
            if jockey_info.get("name") and jockey_info["name"] != jockey.name:
                jockey.name = jockey_info["name"]
                updated += 1
            # Rate limiting
            time.sleep(0.5)
        except Exception:
            errors += 1
            continue

    db.commit()

    return {
        "status": "completed",
        "total": len(jockeys),
        "updated": updated,
        "errors": errors,
    }
