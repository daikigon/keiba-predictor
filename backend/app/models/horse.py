from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    """Return current UTC datetime"""
    return datetime.now(timezone.utc)


class Horse(Base):
    __tablename__ = "horses"

    horse_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    sex: Mapped[str] = mapped_column(String(5), nullable=False)
    birth_year: Mapped[int] = mapped_column(Integer, nullable=False)

    father: Mapped[Optional[str]] = mapped_column(String(50))
    mother: Mapped[Optional[str]] = mapped_column(String(50))
    mother_father: Mapped[Optional[str]] = mapped_column(String(50))
    trainer: Mapped[Optional[str]] = mapped_column(String(50))
    owner: Mapped[Optional[str]] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    # Relationships
    entries: Mapped[list["Entry"]] = relationship(back_populates="horse")


from app.models.race import Entry
