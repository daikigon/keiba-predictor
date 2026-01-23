from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    """Return current UTC datetime"""
    return datetime.now(timezone.utc)


class Race(Base):
    __tablename__ = "races"

    race_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    race_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default="central", index=True
    )  # "central", "local", "banei"
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    course: Mapped[str] = mapped_column(String(10), nullable=False)
    race_number: Mapped[int] = mapped_column(Integer, nullable=False)
    race_name: Mapped[Optional[str]] = mapped_column(String(100))
    distance: Mapped[int] = mapped_column(Integer, nullable=False)
    track_type: Mapped[str] = mapped_column(String(10), nullable=False)
    weather: Mapped[Optional[str]] = mapped_column(String(10))
    condition: Mapped[Optional[str]] = mapped_column(String(10))
    grade: Mapped[Optional[str]] = mapped_column(String(10))
    num_horses: Mapped[Optional[int]] = mapped_column(Integer)  # 頭数
    venue_detail: Mapped[Optional[str]] = mapped_column(String(20))  # 開催 (例: "1京都2")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    
    # Relationships
    entries: Mapped[list["Entry"]] = relationship(back_populates="race")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="race")


class Entry(Base):
    __tablename__ = "entries"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("races.race_id"), nullable=False, index=True
    )
    horse_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("horses.horse_id"), nullable=False, index=True
    )
    jockey_id: Mapped[Optional[str]] = mapped_column(
        String(20), ForeignKey("jockeys.jockey_id")
    )
    
    frame_number: Mapped[Optional[int]] = mapped_column(Integer)
    horse_number: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[Optional[float]] = mapped_column()
    horse_weight: Mapped[Optional[int]] = mapped_column(Integer)
    weight_diff: Mapped[Optional[int]] = mapped_column(Integer)
    
    odds: Mapped[Optional[float]] = mapped_column()
    popularity: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Results (after race)
    result: Mapped[Optional[int]] = mapped_column(Integer)
    finish_time: Mapped[Optional[str]] = mapped_column(String(10))
    margin: Mapped[Optional[str]] = mapped_column(String(20))
    corner_position: Mapped[Optional[str]] = mapped_column(String(20))
    last_3f: Mapped[Optional[float]] = mapped_column()
    pace: Mapped[Optional[str]] = mapped_column(String(20))  # ペース (例: "35.4-38.1")
    prize_money: Mapped[Optional[int]] = mapped_column(Integer)  # 賞金 (万円)
    winner_or_second: Mapped[Optional[str]] = mapped_column(String(50))  # 勝ち馬(2着馬)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    # Relationships
    race: Mapped["Race"] = relationship(back_populates="entries")
    horse: Mapped["Horse"] = relationship(back_populates="entries")
    jockey: Mapped[Optional["Jockey"]] = relationship(back_populates="entries")


# Import for type hints
from app.models.horse import Horse
from app.models.jockey import Jockey
from app.models.prediction import Prediction
