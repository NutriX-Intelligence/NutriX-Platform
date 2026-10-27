import pytest
from PIL import Image

from ms1_cv.cv_engine import MealSession, NutriXCVEngine


@pytest.fixture()
def frame(tmp_path):
    # mock mode keys off the filename: "apple" -> class "apple" at 95% confidence
    path = tmp_path / "apple.jpg"
    Image.new("RGB", (64, 48)).save(path)
    return str(path)


def _engine(tmp_path, suppressed):
    engine = NutriXCVEngine(mock_mode=True, confidence_threshold=0.3, suppressed_classes=suppressed)
    engine.pending_dir = str(tmp_path)  # don't pollute dataset/pending
    return engine


def test_suppressed_class_is_unidentified_with_no_hint(tmp_path, frame):
    ok, result = _engine(tmp_path, {"apple"}).process_scale_event(frame, 150.0, MealSession())

    assert ok is False
    assert result["status"] == "unidentified"
    assert result["fallback_class"] is None
    assert "Suppressed class" in result["reason"]


def test_non_suppressed_class_still_identified(tmp_path, frame):
    ok, result = _engine(tmp_path, {"lassi", "kulfi"}).process_scale_event(frame, 150.0, MealSession())

    assert ok is True and result["status"] == "identified"
    assert result["addition"]["food_name"] == "apple"


def test_suppressed_classes_default_from_env(monkeypatch):
    monkeypatch.setenv("YOLO_SUPPRESSED_CLASSES", " Lassi , KULFI ,")
    assert NutriXCVEngine(mock_mode=True).suppressed_classes == {"lassi", "kulfi"}
