"""Lecture-hall catalogue that instructors pick session venues from.

Sessions keep their own venue_name/venue_latitude/venue_longitude/
geofence_radius_meters columns; picking a venue copies the catalogue values
into them, so check-in geofencing (main._effective_venue) is unchanged and
editing a venue later never moves existing sessions.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.database import get_read_db
from app.models import User, Venue

router = APIRouter(prefix="/api/v1/venues", tags=["venues"])


def serialize_venue(venue: Venue) -> dict:
    return {
        "id": venue.id,
        "code": venue.code,
        "name": venue.name,
        "latitude": venue.latitude,
        "longitude": venue.longitude,
        "default_radius_meters": venue.default_radius_meters,
    }


# Both spellings so Module 4 can call /venues or /venues/ without a 307 redirect.
@router.get("", include_in_schema=False)
@router.get("/")
def list_venues(
    current_user: User = Depends(require_roles("instructor", "admin", read_only=True)),
    db: Session = Depends(get_read_db),
):
    venues = db.query(Venue).filter(Venue.is_active.is_(True)).order_by(Venue.code).all()
    return {"items": [serialize_venue(venue) for venue in venues], "total": len(venues)}


def find_venue(db: Session, value: str | None) -> Venue | None:
    """Match a catalogue venue by code first, then by display name (case-insensitive)."""
    key = (value or "").strip().lower()
    if not key:
        return None
    return (
        db.query(Venue).filter(func.lower(Venue.code) == key).first()
        or db.query(Venue).filter(func.lower(Venue.name) == key).first()
    )


def apply_venue_selection(
    db: Session,
    fields: dict,
    *,
    previous_name: str | None = None,
    fill_default_radius: bool = True,
) -> None:
    """Resolve ``fields["venue_name"]`` against the catalogue, in place.

    * Catalogue match: the venue's name and coordinates replace whatever the
      client sent; the venue's default radius fills a missing radius when
      ``fill_default_radius`` (session create).
    * Deactivated match: 400.
    * No match: kept as free text for API-spec/test compatibility. If the name
      changed and no coordinates came with it (PATCH), the previous venue's
      coordinates are cleared so the session falls back to the course venue
      instead of geofencing at the old hall under a new label.
    """
    if "venue_name" not in fields:
        return
    name = fields["venue_name"]
    venue = find_venue(db, name)
    if venue is not None:
        if not venue.is_active:
            raise HTTPException(status_code=400, detail="Venue is not available")
        fields["venue_name"] = venue.name
        fields["venue_latitude"] = venue.latitude
        fields["venue_longitude"] = venue.longitude
        if fill_default_radius and fields.get("geofence_radius_meters") is None:
            fields["geofence_radius_meters"] = venue.default_radius_meters
        return
    if name != previous_name:
        fields.setdefault("venue_latitude", None)
        fields.setdefault("venue_longitude", None)
