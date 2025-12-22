from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    """Return current UTC datetime"""
    return datetime.now(timezone.utc)


class Jockey(Base):
    __tablename__ = "jockeys"

    jockey_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    win_rate: Mapped[Optional[float]] = mapped_column(Float)
    place_rate: Mapped[Optional[float]] = mapped_column(Float)
    show_rate: Mapped[Optional[float]] = mapped_column(Float)

    # リーディングデータ
    year_rank: Mapped[Optional[int]] = mapped_column(Integer)  # 年間リーディング順位
    year_wins: Mapped[Optional[int]] = mapped_column(Integer)  # 年間勝利数
    year_rides: Mapped[Optional[int]] = mapped_column(Integer)  # 年間騎乗数
    year_earnings: Mapped[Optional[int]] = mapped_column(Integer)  # 年間獲得賞金（万円）

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    # Relationships
    entries: Mapped[list["Entry"]] = relationship(back_populates="jockey")


from app.models.race import Entry
