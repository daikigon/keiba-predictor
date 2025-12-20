"""Tests for service functions"""
import pytest
from datetime import date

from app.services import race_service, prediction_service
from app.models import Race, Entry, Horse, Jockey


class TestRaceService:
    """Tests for race_service"""

    def test_get_races_by_date(self, test_db, sample_race):
        """Test getting races by date"""
        total, races = race_service.get_races_by_date(
            test_db, target_date=date(2024, 12, 22)
        )

        assert total == 1
        assert len(races) == 1
        assert races[0].race_id == sample_race.race_id

    def test_get_races_by_date_no_match(self, test_db, sample_race):
        """Test getting races with no matching date"""
        total, races = race_service.get_races_by_date(
            test_db, target_date=date(2025, 1, 1)
        )

        assert total == 0
        assert len(races) == 0

    def test_get_race_by_id(self, test_db, sample_race):
        """Test getting a race by ID"""
        race = race_service.get_race_by_id(test_db, sample_race.race_id)

        assert race is not None
        assert race.race_id == sample_race.race_id

    def test_get_race_by_id_not_found(self, test_db):
        """Test getting a non-existent race"""
        race = race_service.get_race_by_id(test_db, "nonexistent")

        assert race is None

    def test_save_race(self, test_db):
        """Test saving a new race"""
        race_data = {
            "race_id": "202405010101",
            "date": date(2024, 12, 21),
            "course": "東京",
            "race_number": 1,
            "race_name": "テストレース",
            "distance": 1600,
            "track_type": "芝",
        }

        race = race_service.save_race(test_db, race_data)

        assert race.race_id == "202405010101"
        assert race.course == "東京"

    def test_save_race_update(self, test_db, sample_race):
        """Test updating an existing race"""
        race_data = {
            "race_id": sample_race.race_id,
            "weather": "曇",
        }

        race = race_service.save_race(test_db, race_data)

        assert race.weather == "曇"


class TestPredictionService:
    """Tests for prediction_service"""

    def test_create_prediction(self, test_db, sample_race, sample_entry):
        """Test creating a prediction"""
        prediction = prediction_service.create_prediction(
            test_db, sample_race.race_id
        )

        assert prediction is not None
        assert prediction.race_id == sample_race.race_id
        assert "predictions" in prediction.results_json

    def test_create_prediction_race_not_found(self, test_db):
        """Test creating prediction for non-existent race"""
        with pytest.raises(ValueError, match="not found"):
            prediction_service.create_prediction(test_db, "nonexistent")

    def test_get_prediction_by_race(self, test_db, sample_prediction):
        """Test getting prediction by race"""
        prediction = prediction_service.get_prediction_by_race(
            test_db, sample_prediction.race_id
        )

        assert prediction is not None
        assert prediction.id == sample_prediction.id

    def test_create_history(self, test_db, sample_prediction):
        """Test creating history"""
        history = prediction_service.create_history(
            test_db,
            prediction_id=sample_prediction.id,
            bet_type="単勝",
            bet_detail="1",
            bet_amount=1000,
        )

        assert history.bet_type == "単勝"
        assert history.bet_amount == 1000

    def test_update_history_result(self, test_db, sample_prediction):
        """Test updating history result"""
        history = prediction_service.create_history(
            test_db,
            prediction_id=sample_prediction.id,
            bet_type="単勝",
            bet_detail="1",
            bet_amount=1000,
        )

        updated = prediction_service.update_history_result(
            test_db,
            history_id=history.id,
            is_hit=True,
            payout=3500,
        )

        assert updated.is_hit is True
        assert updated.payout == 3500

    def test_get_history(self, test_db, sample_prediction):
        """Test getting history with summary"""
        # Create some history entries
        prediction_service.create_history(
            test_db, sample_prediction.id, "単勝", "1", 1000
        )

        total, history_list, summary = prediction_service.get_history(test_db)

        assert total == 1
        assert len(history_list) == 1
        assert "total_bets" in summary


class TestMLPredictor:
    """Tests for ML predictor module"""

    def test_feature_columns(self):
        """Test that feature columns are defined"""
        from app.services.predictor import get_feature_columns

        columns = get_feature_columns()

        assert len(columns) > 0
        assert "distance" in columns
        assert "odds" in columns
        assert "jockey_win_rate" in columns

    def test_feature_extractor_init(self, test_db):
        """Test FeatureExtractor initialization"""
        from app.services.predictor import FeatureExtractor

        extractor = FeatureExtractor(test_db)

        assert extractor.db is not None

    def test_feature_extractor_empty_race(self, test_db):
        """Test feature extraction for race with no entries"""
        from app.services.predictor import FeatureExtractor
        from app.models import Race
        from datetime import date

        # Create a race with no entries
        race = Race(
            race_id="test_empty_race",
            date=date(2024, 12, 22),
            course="東京",
            race_number=1,
            distance=2000,
            track_type="芝",
        )
        test_db.add(race)
        test_db.commit()

        extractor = FeatureExtractor(test_db)
        df = extractor.extract_race_features(race)

        assert df.empty

    def test_predictor_model_init(self):
        """Test HorseRacingPredictor initialization"""
        from app.services.predictor import HorseRacingPredictor

        predictor = HorseRacingPredictor(model_version="test_v1")

        assert predictor.model_version == "test_v1"
        assert predictor.model is None  # Model not trained yet

    def test_get_model(self):
        """Test get_model function"""
        from app.services.predictor import get_model

        predictor = get_model("test_version")

        assert predictor is not None
        assert predictor.model_version == "test_version"

    def test_prediction_with_baseline(self, test_db, sample_race, sample_entry):
        """Test prediction falls back to baseline when no ML model"""
        prediction = prediction_service.create_prediction(
            test_db, sample_race.race_id
        )

        assert prediction is not None
        results = prediction.results_json
        assert "predictions" in results
        assert "model_type" in results
        # Should use baseline when no trained model
        assert results["model_type"] == "baseline"
