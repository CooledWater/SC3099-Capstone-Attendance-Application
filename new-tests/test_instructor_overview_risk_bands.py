"""Course histogram bands, using the existing isolated SQLite fixture."""
from datetime import datetime, timedelta

from test_ta_scope import world
from app.models import CheckIn, Session as Meeting, User


def test_overview_bands_boundaries_and_legacy_bins(world):
    call, db = world
    db.query(CheckIn).filter(CheckIn.session_id == "m_a").delete()
    for index, risk in enumerate([0, 0.1, 0.2999, 0.3, 0.4999, 0.5, 0.9, 1]):
        uid = f"risk-student-{index}"
        db.add(User(id=uid, email=f"{uid}@example.edu", full_name=uid, role="student", hashed_password="unused"))
        db.add(CheckIn(session_id="m_a", student_id=uid, status="approved", risk_score=risk))
    db.commit()
    response = call("ia", "/stats/courses/A/overview")
    assert response.status_code == 200, response.text
    risk = response.json()["risk_distribution"]
    assert risk["scored_count"] == 8
    assert risk["bands"] == [
        {"key": "low", "count": 3}, {"key": "medium", "count": 2}, {"key": "high", "count": 3},
    ]
    assert len(risk["bins"]) == 10
    assert sum(item["count"] for item in risk["bins"]) == 8
    # The other course's score must not leak into these counts.
    assert call("ib", "/stats/courses/A/overview").status_code == 403
    assert call("t1", "/stats/courses/A/overview").status_code == 403


def test_overview_empty_bands_respect_period_and_held_sessions(world):
    call, db = world
    future = datetime.utcnow() + timedelta(days=10)
    response = call("ia", "/stats/courses/A/overview", start_date=future.isoformat(), end_date=(future + timedelta(days=7)).isoformat())
    risk = response.json()["risk_distribution"]
    assert risk["scored_count"] == 0
    assert [item["count"] for item in risk["bands"]] == [0, 0, 0]
    db.get(Meeting, "m_a").status = "cancelled"
    db.commit()
    assert call("ia", "/stats/courses/A/overview").json()["risk_distribution"] == risk
