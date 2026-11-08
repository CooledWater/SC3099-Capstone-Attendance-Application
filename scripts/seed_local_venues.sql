-- Optional starter rows for the `venues` table on a fresh local PostgreSQL database.
--
-- The backend creates the table itself on first start (SQLAlchemy create_all), so start
-- the stack first, then run:
--   Get-Content scripts/seed_local_venues.sql | docker compose exec -T postgres psql -U saiv -d saiv
--
-- Only venues with confirmed coordinates are listed. Add other lecture halls with measured
-- coordinates (never guessed ones) using the same INSERT shape. Safe to re-run: an existing
-- code is left untouched.

INSERT INTO venues (id, code, name, latitude, longitude, default_radius_meters, is_active, created_at, updated_at)
VALUES
    (gen_random_uuid()::text, 'LT26', 'Lecture Theatre 26', 1.3434326, 103.6815837, 100.0, true,
     now() AT TIME ZONE 'utc', now() AT TIME ZONE 'utc'),
    (gen_random_uuid()::text, 'LT23', 'Lecture Theatre 23', 1.342867815668114, 103.68171283389401, 100.0, true,
     now() AT TIME ZONE 'utc', now() AT TIME ZONE 'utc')
ON CONFLICT (code) DO NOTHING;

SELECT code, name, latitude, longitude, default_radius_meters, is_active FROM venues ORDER BY code;
