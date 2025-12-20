from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    """Return current UTC datetime"""
    return datetime.now(timezone.utc)


class Training(Base):
    """調教データモデル"""
    __tablename__ = "trainings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    race_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("races.race_id"), nullable=False, index=True
    )
    horse_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("horses.horse_id"), nullable=False, index=True
    )
    horse_number: Mapped[Optional[int]] = mapped_column(Integer)

    # 調教コース (栗東坂路, 美浦南W, etc.)
    training_course: Mapped[Optional[str]] = mapped_column(String(50))

    # 調教タイム
    training_time: Mapped[Optional[str]] = mapped_column(String(20))

    # ラップタイム (12.3-11.8-12.0 形式)
    lap_times: Mapped[Optional[str]] = mapped_column(String(50))

    # 調教評価 (A, B, C, D, E, S)
    training_rank: Mapped[Optional[str]] = mapped_column(String(5))

    # 追切日
    training_date: Mapped[Optional[str]] = mapped_column(String(20))

    # 騎乗者
    rider: Mapped[Optional[str]] = mapped_column(String(50))

    # コメント/備考
    comment: Mapped[Optional[str]] = mapped_column(String(200))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    # Relationships
    race: Mapped["Race"] = relationship()
    horse: Mapped["Horse"] = relationship()


from app.models.race import Race
from app.models.horse import Horse
