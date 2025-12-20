from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.horse import Horse
from app.models.race import Entry

router = APIRouter()


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
                "race_name": race.race_name,
                "course": race.course,
                "distance": race.distance,
                "track_type": race.track_type,
                "horse_number": e.horse_number,
                "result": e.result,
                "odds": e.odds,
                "popularity": e.popularity,
                "jockey_name": e.jockey.name if e.jockey else None,
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
