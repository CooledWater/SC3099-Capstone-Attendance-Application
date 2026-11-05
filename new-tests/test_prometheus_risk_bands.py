"""Risk categories match the documented inclusive medium/high boundaries."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from prometheus_client import CollectorRegistry, Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "module2-backend"))
from app import prometheus_metrics as metrics


@pytest.mark.parametrize("score, expected", [
    (0.0, "low"), (0.299999, "low"), (0.3, "medium"),
    (0.499999, "medium"), (0.5, "high"), (0.699999, "high"),
    (0.7, "critical"), (1.0, "critical"),
])
def test_checkin_increments_exactly_one_documented_band(monkeypatch, score, expected):
    registry = CollectorRegistry()
    counter = Counter("checkin_risk_level_total", "Risk levels", ["band"], registry=registry)
    for band in ("low", "medium", "high", "critical"):
        counter.labels(band=band)
    monkeypatch.setattr(metrics, "CHECKIN_RISK_BANDS", counter)
    for name in ("CHECKIN_ATTEMPTS", "CHECKIN_SUCCESS", "CHECKIN_OUTCOMES", "CHECKIN_RISK"):
        monkeypatch.setattr(metrics, name, MagicMock())
    metrics.record_checkin("approved", score)
    for band in ("low", "medium", "high", "critical"):
        assert registry.get_sample_value("checkin_risk_level_total", {"band": band}) == (1 if band == expected else 0)
    metrics.CHECKIN_RISK.observe.assert_called_once_with(score)


def test_all_four_level_series_exist_before_first_checkin():
    samples = metrics.CHECKIN_RISK_BANDS.collect()[0].samples
    bands = {sample.labels["band"] for sample in samples if sample.name == "checkin_risk_level_total"}
    assert bands == {"low", "medium", "high", "critical"}
