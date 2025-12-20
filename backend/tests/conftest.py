import pytest
from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import Race, Entry, Horse, Jockey, Prediction, History


@pytest.fixture(scope="function")
def test_db():
    """Create a test database in memory"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def sample_race(test_db):
    """Create a sample race for testing"""
    race = Race(
        race_id="202405050811",
        date=date(2024, 12, 22),
        course="中山",
        race_number=11,
        race_name="有馬記念",
        distance=2500,
        track_type="芝",
        weather="晴",
        condition="良",
        grade="G1",
    )
    test_db.add(race)
    test_db.commit()
    return race


@pytest.fixture
def sample_horse(test_db):
    """Create a sample horse for testing"""
    horse = Horse(
        horse_id="2019104308",
        name="ドウデュース",
        sex="牡",
        birth_year=2019,
        father="ハーツクライ",
        mother="ダストアンドダイヤモンズ",
    )
    test_db.add(horse)
    test_db.commit()
    return horse


@pytest.fixture
def sample_jockey(test_db):
    """Create a sample jockey for testing"""
    jockey = Jockey(
        jockey_id="01167",
        name="武豊",
        win_rate=15.2,
        place_rate=28.5,
        show_rate=38.2,
    )
    test_db.add(jockey)
    test_db.commit()
    return jockey


@pytest.fixture
def sample_entry(test_db, sample_race, sample_horse, sample_jockey):
    """Create a sample entry for testing"""
    entry = Entry(
        race_id=sample_race.race_id,
        horse_id=sample_horse.horse_id,
        jockey_id=sample_jockey.jockey_id,
        frame_number=1,
        horse_number=1,
        weight=57.0,
        odds=3.5,
        popularity=1,
    )
    test_db.add(entry)
    test_db.commit()
    return entry


@pytest.fixture
def sample_prediction(test_db, sample_race):
    """Create a sample prediction for testing"""
    prediction = Prediction(
        race_id=sample_race.race_id,
        model_version="v0.1.0",
        results_json={
            "predictions": [
                {"horse_number": 1, "predicted_rank": 1, "probability": 0.35},
                {"horse_number": 2, "predicted_rank": 2, "probability": 0.25},
            ],
            "recommended_bets": [
                {"bet_type": "単勝", "detail": "1", "confidence": "high"},
            ],
        },
    )
    test_db.add(prediction)
    test_db.commit()
    return prediction
