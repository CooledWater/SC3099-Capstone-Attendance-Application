# Geolocation testing (Friday 23 October 2026)

`setup_geotest.ps1` prepares a GPS-only test of the check-in geofence through the backend API. It never connects to the database directly.

## What the script creates

| Course | Radius | Approved | Flagged | Rejected |
|---|---|---|---|---|
| GEO-T1 | 25 m | under 25 m | 25-50 m | over 50 m |
| GEO-T2 | 50 m | under 50 m | 50-100 m | over 100 m |
| GEO-T3 | 100 m | under 100 m | 100-200 m | over 200 m |
| GEO-T4 | 200 m | under 200 m | 200-400 m | over 400 m |
| GEO-T5 | 400 m | under 400 m | 400-800 m | over 800 m |

- **5 courses.** All five share one venue (the coordinates you pass in) and are assigned to `instructor@gmail.com`.
- **50 enrolments.** The 10 existing test students (`student1@gmail.com` and `sc3099.geotest.student02..10@example.com`) are enrolled in every course. No accounts are created.
- **5 sessions.** There is one per course, named `GEO-Tn GPS test 2026-10-23`.
  - Liveness, face match and motion checks are all turned off, so only GPS distance decides the result.
  - Check-in is open from the start time to the end time.
  - The backend makes the session `active` at the start time and `closed` at the end time.

Which account does what:
- **Admin:** creates the courses. The script asks for the admin login only when a course is missing.
- **Instructor:** fixes the courses, does the enrolments, and creates and edits the sessions. The instructor creates the sessions so that they own them.

Re-running is safe:
- Records are matched by course code, student email and session name. Anything that already matches is left alone.
- If a test session is still `scheduled` and its time, flags or venue differ from what you passed in, it is updated.
- Sessions that are already active or closed are never edited.
- The script stops before writing anything if a `GEO-T*` code belongs to another instructor or has been deactivated.
- Nothing else is touched: no other courses, students or sessions.

## Running it

Before you start:
- The backend is running on `http://localhost:8000` against the shared Supabase project.
- You have the venue coordinates. Measure them on site (for example, drop a pin in Google Maps and copy the latitude and longitude to 6 decimal places). Never guess them.
- You have the instructor and admin passwords. They are typed at hidden prompts and are never printed or saved. The test student passwords are in the git-ignored `.secrets/sc3099-test-accounts.csv`.

```powershell
cd C:\Users\Malishka\Documents\SC3099-Capstone-Attendance-Application
$geo = @{ Latitude = <LAT>; Longitude = <LNG>; VenueName = "<venue name>"; StartLocal = "2026-10-23 <HH:mm>"; DurationMinutes = <minutes> }

# 1. Dry run: reads and prints the plan, changes nothing
powershell -ExecutionPolicy Bypass -File .\scripts\setup_geotest.ps1 @geo

# 2. Apply: creates and fixes the records, then checks them and prints a summary
powershell -ExecutionPolicy Bypass -File .\scripts\setup_geotest.ps1 @geo -Apply

# 3. Results: read-only check-in report (use it during and after testing)
powershell -ExecutionPolicy Bypass -File .\scripts\setup_geotest.ps1 @geo -ShowResults
```

- `StartLocal` is Singapore time.
- Run `-Apply` before the start time, because a session cannot be created with a start time in the past.
- The summary lists each course code, radius, enrolment count (`10/10`), session ID, start and end time (SGT), status, and `PASS` or `FAIL`.

## On Friday

1. **Check the student app on a phone first.** Students' phones must open the student app over **HTTPS**, because browsers only share location on secure pages. The backend must also accept requests from that address: right now CORS allows only `localhost:3000` and `localhost:8501`, and the app's default API URL is `localhost`. Sort this out and test it on a phone before Friday.
2. Before testing, mark standing points at measured distances from the venue pin, for example 0, 15, 35, 60, 90, 150, 250, 350, 600 and 900 m. Measure outdoors, because indoor GPS readings can be off by 20-50 m.
3. Give each student account one standing point. One person can sign in to several accounts in turn.
4. At their point, each student checks in to all 5 sessions in the student app. The session list shows sessions from every course in the shared database, so pick the `GEO-Tn GPS test` ones.
   - The app still asks for one photo. The backend ignores it for these sessions.
   - Allow precise location.
   - The app shows the GPS accuracy. Over 100 m, wait for a better fix before submitting.
5. Note the accuracy the phone shows for each check-in. The backend saves it but it does not affect the result.

**Each student can check in only once per session.** A second attempt gets "Already checked in to this session". To repeat a test, use another student account, or create new sessions by re-running `-Apply` with a different `StartLocal` date. The session name contains the date.

## Reading the results

- **Script:** `-ShowResults` lists every check-in per session with the student, time, `distance_from_venue_meters`, status, expected status, risk score and risk factors. A `CHECK` in the Match column means the backend's result differs from the table above.
- **Dashboard:** log in as the instructor, then use the Check-ins tab or the CSV export on a session. The Sessions tab only loads the first 100 sessions in the shared database, so a test session may not appear there. If so, use the script.
- **API:** `GET /api/v1/checkins/session/{session_id}` with an instructor token.

How the backend decides (`main.py` `_assess_checkin_geofence`, with the default risk threshold of 0.5):

| Status | When | What you will see |
|---|---|---|
| `approved` | distance < radius | risk under 0.5, no `geo_out_of_bounds` |
| `flagged` | radius <= distance <= 2 x radius | risk 0.5-1.0; `geo_out_of_bounds` (medium) once the distance is over the radius |
| `rejected` | distance > 2 x radius | risk 1.0, `geo_out_of_bounds` (high); this cannot be overridden |

- `risk_score` is `min(distance / radius, 2) / 2`.
- `geo_accuracy_low` only appears when the GPS accuracy is worse than the radius. It is informational (weight 0) and does not change the status.
- The distance is calculated from the coordinates the phone reports. A wrong result usually means poor GPS, not a backend fault. Compare the distance against your measured standing point.
