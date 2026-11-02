"""Focused TA overview browser check with isolated API fixtures, no shared writes."""
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, expect

ORIGIN = os.getenv("DASHBOARD_TEST_ORIGIN", "http://127.0.0.1:5179")
COURSES = [{"id": "A", "code": "SC3099", "name": "Software Engineering"}, {"id": "B", "code": "SC4000", "name": "Other assigned course"}]
SESSION = {"id": "s", "course_id": "A", "name": "Lecture 9", "status": "active", "scheduled_start": "2026-10-28T02:00:00Z", "scheduled_end": "2026-10-28T03:00:00Z"}
OTHER = {**SESSION, "id": "other", "course_id": "B", "name": "Tutorial", "status": "closed"}
labels = ["flagged", "appealed", "pending", "approved", "rejected"] + ["approved"] * 33 + ["pending", "flagged", "flagged", "appealed"]
records = []
minutes = [0] * 4 + [5] * 16 + [10] * 12 + [15] * 6 + [20] * 3 + [25]
for i, status in enumerate(labels):
    when = datetime(2026, 10, 28, 2, tzinfo=timezone.utc) + timedelta(minutes=minutes[i], seconds=i)
    records.append({"student_id": f"u{i}", "student_name": ["Aisha Tan", "Ryan Lim", "Mei Chen", "Daniel Lee", "Sarah Ong"][i] if i < 5 else f"Student {i}",
                    "student_email": f"s{i}@example.edu", "checkin_id": f"c{i}", "id": f"c{i}", "session_id": "s", "course_id": "A", "attendance": "present",
                    "checked_in_at": when.isoformat(), "status": status,
                    "risk_score": None if status == "pending" else {"approved": 0.1667, "flagged": 0.65, "appealed": 0.58, "rejected": 0.82}[status],
                    "appeal_reason": "Please review my check-in." if status == "appealed" else None,
                    "risk_factors": [{"type": "device_unknown", "severity": "medium", "weight": 0.15}]})
events = []

def session_stats(sid):
    rows = records if sid == "s" else []
    counts = {key: sum(row["status"] == key for row in rows) for key in ("approved", "pending", "flagged", "appealed", "rejected")}
    scores = [row["risk_score"] for row in rows if row["risk_score"] is not None]
    return {"session_id": sid, "course_id": "A" if sid == "s" else "B", "course_code": "SC3099" if sid == "s" else "SC4000", "session_name": "Lecture 9" if sid == "s" else "Tutorial",
            "status": "active" if sid == "s" else "closed", "scheduled_start": SESSION["scheduled_start"], "scheduled_end": SESSION["scheduled_end"], "actual_end": None,
            "checkin_opens_at": "2026-10-28T02:00:00Z", "checkin_closes_at": "2026-10-28T03:00:00Z", "server_time": "2026-10-28T02:27:00Z", "timezone": "Asia/Singapore",
            "submitted_count": len(rows), "expected_count": 50, "scored_count": len(scores), "average_risk_score": sum(scores) / len(scores) if scores else 0,
            "by_status": counts, "timeline_bucket_minutes": 5, "pre_opening_count": 0,
            "checkin_timeline": [{"minute": minute, "count": count} for minute, count in sorted(Counter(minutes if rows else []).items())],
            "today": {"date": "2026-10-28", "total": 2, "breakdown": {"active": 1, "scheduled": 1, "closed": 0, "cancelled": 0}}, "recent_review_activity": events if rows else []}

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless=True)
        page = browser.new_page(viewport={"width": 1180, "height": 980})
        errors, forbidden_calls = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        page.route('https://fonts.gstatic.com/**', lambda route: route.abort())
        def mock(route):
            path = urlparse(route.request.url).path
            params = parse_qs(urlparse(route.request.url).query)
            if any(value in path for value in ("/stats/overview", "/stats/courses", "/audit/", "/enrollments/")):
                forbidden_calls.append(path)
                route.fulfill(status=403, json={"detail": "Forbidden"})
                return
            if path.endswith('/auth/dashboard/refresh'): data = {"access_token": "test"}
            elif path.endswith('/users/me'): data = {"id": "ta", "role": "ta", "email": "ta@example.edu", "full_name": "TA"}
            elif path.endswith('/courses/my-courses'): data = {"items": COURSES, "total": 2}
            elif path.endswith('/sessions/'):
                data = {"items": [OTHER] if params.get('course_id') == ['B'] else [SESSION], "total": 1}
            elif '/stats/sessions/' in path: data = session_stats(path.rsplit('/', 1)[-1])
            elif path.endswith('/attendance'):
                sid = path.split('/')[-2]
                data = {"session_id": sid, "course_id": "A" if sid == "s" else "B", "items": records if sid == "s" else []}
            elif path.endswith('/checkins/flagged'):
                rows = [row for row in records if row['status'] in ('flagged', 'appealed')]
                data = {"items": rows, "total": len(rows)}
            elif path.endswith('/review'):
                row = next(row for row in records if row['id'] == path.split('/')[-2])
                previous = row['status']
                row['status'] = json.loads(route.request.post_data)['status']
                events.insert(0, {"id": "e1", "session_id": "s", "session_name": "Lecture 9", "action": "checkin_reviewed", "decision": row['status'], "previous_status": previous, "timestamp": "2026-10-28T02:27:00Z"})
                data = {"id": row['id'], "status": row['status']}
            elif '/checkins/' in path: data = next(row for row in records if row['id'] == path.rsplit('/', 1)[-1])
            else: data = {"items": [], "total": 0}
            route.fulfill(status=200, content_type='application/json', body=json.dumps(data))
        page.route('**/api/v1/**', mock)
        page.goto(ORIGIN + '/dashboard/', wait_until='domcontentloaded', timeout=60000)
        expect(page.get_by_label('TA overview session')).to_have_value('s')
        expect(page.get_by_text('84%', exact=True)).to_be_visible()
        roster = page.get_by_role('region', name='Session check-ins', exact=True)
        expect(roster.get_by_text('Session check-ins', exact=True)).to_be_visible()
        output = Path(os.getenv('TEMP', '.')) / 'ta-overview-preview'
        output.mkdir(exist_ok=True)
        page.screenshot(path=str(output / 'desktop.png'), full_page=True)
        page.get_by_role('button', name='Needs review', exact=False).click()
        expect(roster.get_by_role('button', name='Review', exact=True)).to_have_count(5)
        roster.get_by_role('button', name='Review', exact=True).first.click()
        detail = page.get_by_role('region', name='Check-in details', exact=True)
        expect(detail.get_by_text('Risk factors', exact=True)).to_be_visible()
        detail.get_by_role('button', name='Approve', exact=True).click()
        expect(page.get_by_text('1 appealed', exact=False)).to_be_visible()
        expect(page.get_by_role('region', name='Recent review activity', exact=True).get_by_text('Check-in approved', exact=True)).to_be_visible()
        page.get_by_role('region', name='Recent review activity', exact=True).screenshot(path=str(output / 'review-card-desktop.png'))
        detail.get_by_role('button', name='Close', exact=True).click()
        expect(roster.get_by_role('button', name='Review', exact=True)).to_have_count(4)
        roster.get_by_role('button', name='All statuses', exact=True).click()
        page.get_by_role('button', name='rejected', exact=False).last.click()
        expect(roster.get_by_role('button', name='View details', exact=True)).to_have_count(1)
        roster.get_by_role('button', name='All statuses', exact=True).click()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'full-page horizontal overflow'
        table_scroller = roster.locator('table').locator('..')
        assert table_scroller.evaluate('(el) => el.scrollWidth > el.clientWidth'), 'table should scroll horizontally on mobile'
        assert table_scroller.evaluate('(el) => el.scrollHeight > el.clientHeight'), 'table should scroll vertically'
        page.screenshot(path=str(output / 'mobile.png'), full_page=True)
        page.get_by_role('region', name='Recent review activity', exact=True).screenshot(path=str(output / 'review-card-mobile.png'))
        page.get_by_label('TA overview course').select_option('B')
        expect(page.get_by_label('TA overview session')).to_have_value('other')
        expect(page.get_by_text('No scored check-ins', exact=True)).to_be_visible()
        assert not forbidden_calls, forbidden_calls
        assert not errors, errors
        browser.close()
        print('PASS: TA selectors, KPI/donut roster filters, review refresh, real-event display, course switching and mobile scrolling.')
        print('Screenshots:', output)

if __name__ == '__main__':
    main()
