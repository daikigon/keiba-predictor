"""Tests for database models"""
import pytest
from datetime import date, datetime

from app.models import Race, Entry, Horse, Jockey, Prediction, History


class TestRaceModel:
    """Tests for Race model"""

    def test_create_race(self, test_db):
        """Test creating a race"""
        race = Race(
            race_id="202405050811",
            date=date(2024, 12, 22),
            course="中山",
            race_number=11,
            race_name="有馬記念",
            distance=2500,
            track_type="芝",
            grade="G1",
        )
        test_db.add(race)
        test_db.commit()

        assert race.race_id == "202405050811"
        assert race.course == "中山"
        assert race.distance == 2500
        assert race.track_type == "芝"

    def test_race_entries_relationship(self, test_db, sample_race, sample_entry):
        """Test race-entries relationship"""
        test_db.refresh(sample_race)
        assert len(sample_race.entries) == 1
        assert sample_race.entries[0].horse_number == 1


class TestHorseModel:
    """Tests for Horse model"""

    def test_create_horse(self, test_db):
        """Test creating a horse"""
        horse = Horse(
            horse_id="2019104308",
            name="ドウデュース",
            sex="牡",
            birth_year=2019,
        )
        test_db.add(horse)
        test_db.commit()

        assert horse.name == "ドウデュース"
        assert horse.sex == "牡"
        assert horse.birth_year == 2019


class TestJockeyModel:
    """Tests for Jockey model"""

    def test_create_jockey(self, test_db):
        """Test creating a jockey"""
        jockey = Jockey(
            jockey_id="01167",
            name="武豊",
            win_rate=15.2,
        )
        test_db.add(jockey)
        test_db.commit()

        assert jockey.name == "武豊"
        assert jockey.win_rate == 15.2


class TestEntryModel:
    """Tests for Entry model"""

    def test_create_entry(self, test_db, sample_race, sample_horse, sample_jockey):
        """Test creating an entry"""
        entry = Entry(
            race_id=sample_race.race_id,
            horse_id=sample_horse.horse_id,
            jockey_id=sample_jockey.jockey_id,
            horse_number=5,
            weight=57.0,
        )
        test_db.add(entry)
        test_db.commit()

        assert entry.horse_number == 5
        assert entry.weight == 57.0
        assert entry.horse.name == "ドウデュース"
        assert entry.jockey.name == "武豊"


class TestPredictionModel:
    """Tests for Prediction model"""

    def test_create_prediction(self, test_db, sample_race):
        """Test creating a prediction"""
        prediction = Prediction(
            race_id=sample_race.race_id,
            model_version="v0.1.0",
            results_json={"predictions": []},
        )
        test_db.add(prediction)
        test_db.commit()

        assert prediction.model_version == "v0.1.0"
        assert prediction.race_id == sample_race.race_id


class TestHistoryModel:
    """Tests for History model"""

    def test_create_history(self, test_db, sample_prediction):
        """Test creating a history entry"""
        history = History(
            prediction_id=sample_prediction.id,
            bet_type="単勝",
            bet_detail="1",
            bet_amount=1000,
        )
        test_db.add(history)
        test_db.commit()

        assert history.bet_type == "単勝"
        assert history.bet_amount == 1000

    def test_update_history_result(self, test_db, sample_prediction):
        """Test updating history result"""
        history = History(
            prediction_id=sample_prediction.id,
            bet_type="単勝",
            bet_detail="1",
            bet_amount=1000,
        )
        test_db.add(history)
        test_db.commit()

        history.is_hit = True
        history.payout = 3500
        test_db.commit()

        assert history.is_hit is True
        assert history.payout == 3500
