"""Approved review policy for inconsistent, client-reported GPS history."""
import math
from datetime import timedelta

from app.models import CheckIn

MAX_SPEED_KMH = 1200.0
NOISE_ALLOWANCE_METERS = 1000.0
HISTORY_WINDOW = timedelta(hours=24)


def distance_meters(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((phi2 - phi1) / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371000.0 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, a))))


def assess_impossible_travel(db, student_id, payload, now):
    """Compare with the latest earlier located submission, of any status.

    Subtract both reported uncertainty radii and 1 km before measuring speed.
    Coordinates are untrusted evidence: the result asks for human review.
    No location, identity or prior-check-in identifier is added to the signal.
    """
    previous = (db.query(CheckIn).filter(
        CheckIn.student_id == student_id,
        CheckIn.checked_in_at >= now - HISTORY_WINDOW,
        CheckIn.checked_in_at <= now,
        CheckIn.latitude.isnot(None), CheckIn.longitude.isnot(None),
    ).order_by(CheckIn.checked_in_at.desc(), CheckIn.id).first())
    if previous is None:
        return None
    lat, lon = previous.latitude, previous.longitude
    # Historical imports might predate finite/range validation.
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    accuracy = previous.location_accuracy_meters or 0.0
    if not math.isfinite(accuracy) or accuracy < 0:
        return None
    distance = max(0.0, distance_meters(lat, lon, payload.latitude, payload.longitude)
                   - accuracy - (payload.location_accuracy_meters or 0.0) - NOISE_ALLOWANCE_METERS)
    seconds = (now - previous.checked_in_at).total_seconds()
    # Division-free comparison also handles two submissions at the same instant.
    if distance > MAX_SPEED_KMH / 3.6 * seconds:
        return {'type': 'impossible_travel', 'severity': 'high', 'weight': 0.0}
    return None
