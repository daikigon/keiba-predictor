from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    """Return current UTC datetime"""
    return datetime.now(timezone.utc)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("races.race_id"), nullable=False, index=True
    )
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    results_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    # Relationships
    race: Mapped["Race"] = relationship(back_populates="predictions")
    history: Mapped[list["History"]] = relationship(back_populates="prediction")


class History(Base):
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("predictions.id"), nullable=False
    )

    bet_type: Mapped[str] = mapped_column(String(20), nullable=False)
    bet_detail: Mapped[str] = mapped_column(String(50), nullable=False)
    bet_amount: Mapped[Optional[int]] = mapped_column(Integer)

    is_hit: Mapped[Optional[bool]] = mapped_column(Boolean)
    payout: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    # Relationships
    prediction: Mapped["Prediction"] = relationship(back_populates="history")


from app.models.race import Race
