from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.training import Training
from app.services.scraper import TrainingScraper


def get_training_by_race(db: Session, race_id: str) -> list[Training]:
    """Get training data for a race"""
    stmt = select(Training).where(Training.race_id == race_id)
    return list(db.execute(stmt).scalars().all())


def get_training_by_horse(db: Session, horse_id: str) -> list[Training]:
    """Get training data for a horse"""
    stmt = select(Training).where(Training.horse_id == horse_id).order_by(
        Training.created_at.desc()
    )
    return list(db.execute(stmt).scalars().all())


def scrape_and_save_training(db: Session, race_id: str) -> list[Training]:
    """Scrape training data for a race and save to database"""
    scraper = TrainingScraper()
    training_data = scraper.scrape(race_id)

    saved_trainings = []

    for data in training_data:
        horse_id = data.get("horse_id")
        horse_number = data.get("horse_number")

        if not horse_id and not horse_number:
            continue

        # Check if training data already exists for this race and horse
        stmt = select(Training).where(Training.race_id == race_id)
        if horse_id:
            stmt = stmt.where(Training.horse_id == horse_id)
        elif horse_number:
            stmt = stmt.where(Training.horse_number == horse_number)

        existing = db.execute(stmt).scalar_one_or_none()

        if existing:
            # Update existing record
            if data.get("training_course"):
                existing.training_course = data["training_course"]
            if data.get("training_time"):
                existing.training_time = data["training_time"]
            if data.get("lap_times"):
                existing.lap_times = data["lap_times"]
            if data.get("training_rank"):
                existing.training_rank = data["training_rank"]
            saved_trainings.append(existing)
        else:
            # Create new record
            training = Training(
                race_id=race_id,
                horse_id=horse_id or "",
                horse_number=horse_number,
                training_course=data.get("training_course"),
                training_time=data.get("training_time"),
                lap_times=data.get("lap_times"),
                training_rank=data.get("training_rank"),
            )
            db.add(training)
            saved_trainings.append(training)

    db.commit()

    for training in saved_trainings:
        db.refresh(training)

    return saved_trainings


def save_training(db: Session, training_data: dict) -> Training:
    """Save a single training record"""
    training = Training(
        race_id=training_data["race_id"],
        horse_id=training_data["horse_id"],
        horse_number=training_data.get("horse_number"),
        training_course=training_data.get("training_course"),
        training_time=training_data.get("training_time"),
        lap_times=training_data.get("lap_times"),
        training_rank=training_data.get("training_rank"),
        training_date=training_data.get("training_date"),
        rider=training_data.get("rider"),
        comment=training_data.get("comment"),
    )
    db.add(training)
    db.commit()
    db.refresh(training)
    return training
