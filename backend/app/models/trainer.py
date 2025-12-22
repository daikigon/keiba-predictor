from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    """Return current UTC datetime"""
    return datetime.now(timezone.utc)


class Trainer(Base):
    """調教師モデル"""
    __tablename__ = "trainers"

    trainer_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    # 基本成績
    win_rate: Mapped[Optional[float]] = mapped_column(Float)
    place_rate: Mapped[Optional[float]] = mapped_column(Float)
    show_rate: Mapped[Optional[float]] = mapped_column(Float)

    # リーディングデータ
    year_rank: Mapped[Optional[int]] = mapped_column(Integer)  # 年間リーディング順位
    year_wins: Mapped[Optional[int]] = mapped_column(Integer)  # 年間勝利数
    year_entries: Mapped[Optional[int]] = mapped_column(Integer)  # 年間出走数
    year_earnings: Mapped[Optional[int]] = mapped_column(Integer)  # 年間獲得賞金（万円）

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Sire(Base):
    """種牡馬モデル"""
    __tablename__ = "sires"

    sire_id: Mapped[str] = mapped_column(String(50), primary_key=True)  # 種牡馬名がID
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    # 基本成績
    win_rate: Mapped[Optional[float]] = mapped_column(Float)
    place_rate: Mapped[Optional[float]] = mapped_column(Float)
    show_rate: Mapped[Optional[float]] = mapped_column(Float)

    # リーディングデータ
    year_rank: Mapped[Optional[int]] = mapped_column(Integer)  # 年間リーディング順位
    year_wins: Mapped[Optional[int]] = mapped_column(Integer)  # 年間勝利数
    year_runners: Mapped[Optional[int]] = mapped_column(Integer)  # 年間出走頭数
    year_earnings: Mapped[Optional[int]] = mapped_column(Integer)  # 年間獲得賞金（万円）

    # 条件別成績
    turf_win_rate: Mapped[Optional[float]] = mapped_column(Float)  # 芝勝率
    dirt_win_rate: Mapped[Optional[float]] = mapped_column(Float)  # ダート勝率
    short_win_rate: Mapped[Optional[float]] = mapped_column(Float)  # 短距離（～1400m）勝率
    mile_win_rate: Mapped[Optional[float]] = mapped_column(Float)  # マイル（1401-1800m）勝率
    middle_win_rate: Mapped[Optional[float]] = mapped_column(Float)  # 中距離（1801-2200m）勝率
    long_win_rate: Mapped[Optional[float]] = mapped_column(Float)  # 長距離（2201m～）勝率

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
