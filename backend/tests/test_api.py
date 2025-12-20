"""Tests for API endpoints"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import date

from app.main import app
from app.db.session import get_db


@pytest.fixture
def client(test_db):
    """Create a test client with test database"""

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestRootEndpoints:
    """Tests for root endpoints"""

    def test_root(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert "Keiba Predictor API" in response.json()["message"]

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestRacesAPI:
    """Tests for races API"""

    def test_get_races_empty(self, client):
        """Test getting races when empty"""
        response = client.get("/api/v1/races")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["races"] == []

    def test_get_races_with_data(self, client, sample_race):
        """Test getting races with data"""
        response = client.get("/api/v1/races")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["races"][0]["race_id"] == sample_race.race_id

    def test_get_races_by_date(self, client, sample_race):
        """Test getting races by date"""
        response = client.get("/api/v1/races?target_date=2024-12-22")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_get_races_invalid_date(self, client):
        """Test getting races with invalid date"""
        response = client.get("/api/v1/races?target_date=invalid")
        assert response.status_code == 400

    def test_get_race_detail(self, client, sample_race, sample_entry):
        """Test getting race detail"""
        response = client.get(f"/api/v1/races/{sample_race.race_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["race_id"] == sample_race.race_id
        assert len(data["entries"]) == 1

    def test_get_race_not_found(self, client):
        """Test getting non-existent race"""
        response = client.get("/api/v1/races/nonexistent")
        assert response.status_code == 404


class TestPredictionsAPI:
    """Tests for predictions API"""

    def test_create_prediction(self, client, sample_race, sample_entry):
        """Test creating a prediction"""
        response = client.post(f"/api/v1/predictions?race_id={sample_race.race_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["race_id"] == sample_race.race_id
        assert "results" in data

    def test_create_prediction_race_not_found(self, client):
        """Test creating prediction for non-existent race"""
        response = client.post("/api/v1/predictions?race_id=nonexistent")
        assert response.status_code == 404

    def test_get_prediction(self, client, sample_prediction):
        """Test getting prediction"""
        response = client.get(f"/api/v1/predictions/{sample_prediction.race_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["race_id"] == sample_prediction.race_id

    def test_get_prediction_not_found(self, client):
        """Test getting non-existent prediction"""
        response = client.get("/api/v1/predictions/nonexistent")
        assert response.status_code == 404


class TestHistoryAPI:
    """Tests for history API"""

    def test_get_history_empty(self, client):
        """Test getting history when empty"""
        response = client.get("/api/v1/history")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["history"] == []

    def test_create_history(self, client, sample_prediction):
        """Test creating history"""
        response = client.post(
            f"/api/v1/history?prediction_id={sample_prediction.id}"
            "&bet_type=単勝&bet_detail=1&bet_amount=1000"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["bet_type"] == "単勝"

    def test_update_history_result(self, client, sample_prediction):
        """Test updating history result"""
        # First create history
        create_response = client.post(
            f"/api/v1/history?prediction_id={sample_prediction.id}"
            "&bet_type=単勝&bet_detail=1&bet_amount=1000"
        )
        history_id = create_response.json()["id"]

        # Then update result
        response = client.put(
            f"/api/v1/history/{history_id}/result?is_hit=true&payout=3500"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_hit"] is True
        assert data["payout"] == 3500


class TestStatsAPI:
    """Tests for stats API"""

    def test_get_accuracy_stats(self, client):
        """Test getting accuracy stats"""
        response = client.get("/api/v1/stats/accuracy")
        assert response.status_code == 200
        data = response.json()
        assert "accuracy" in data
        assert "period" in data

    def test_get_scrape_status(self, client):
        """Test getting scrape status"""
        response = client.get("/api/v1/stats/scrape")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "counts" in data
