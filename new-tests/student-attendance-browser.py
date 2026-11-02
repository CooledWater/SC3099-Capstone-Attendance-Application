"""Focused browser smoke check with isolated API fixtures; no shared backend writes.
Run with the dashboard dev server at http://127.0.0.1:5178/dashboard/.
"""
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

ORIGIN = os.getenv("DASHBOARD_TEST_ORIGIN", "http://127.0.0.1:5178")
COURSES = [{"id": "c", "code": "SC3099", "name": "Software Engineering", "instructor_id": "i"}, {"id": "b", "code": "SC1001", "name": "Computing", "instructor_id": "i"}]
DETAIL = {"student_id": "s1", "student_name": "John Doe", "student_email": "john@example.com", "courses": [
    {"course_id": "c", "course_code": "SC3099", "attendance_rate": 0.9167, "sessions_attended": 11, "total_sessions": 12, "average_risk_score": 0.12},
    {"course_id": "b", "course_code": "SC1001", "attendance_rate": 0.5, "sessions_attended": 1, "total_sessions": 2, "average_risk_score": 0.3}],
    "recent_checkins": [{"session_name": name, "course_code": "SC3099", "checked_in_at": when, "status": status} for name, when, status in [
        ("Lecture 9", "2026-10-28T02:02:00Z", "approved"), ("Tutorial 8", "2026-10-23T06:31:00Z", "appealed"),
        ("Lecture 8", "2026-10-21T02:01:00Z", "flagged"), ("Lab 7", "2026-10-16T08:03:00Z", "approved"),
        ("Lecture 7", "2026-10-14T02:00:00Z", "approved")]]}

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", headless=True)
        page = browser.new_page(viewport={"width": 1024, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.add_init_script("""if (!sessionStorage.getItem('instructor:i:tab')) {
            sessionStorage.setItem('instructor:i:tab', 'enrollments');
            sessionStorage.setItem('instructor:i:course', 'c');
        }""")
        def mock(route):
            path = urlparse(route.request.url).path
            if path.endswith('/auth/dashboard/refresh'): data = {"access_token": "test-token"}
            elif path.endswith('/users/me'): data = {"id": "i", "role": "instructor", "email": "instructor@example.com", "full_name": "Instructor"}
            elif path.endswith('/courses/my-courses'): data = {"items": COURSES}
            elif path.endswith('/stats/students/s1'): data = DETAIL
            elif path.endswith('/invitations'): data = {"items": []}
            elif path.endswith('/enrollments/course/c'): data = {"students": [{"id": "enrollment-id", "student_id": "s1", "student_name": "John Doe", "student_email": "john@example.com", "is_active": True, "face_enrolled": True}], "total_records": 1, "active_count": 1, "inactive_count": 0}
            else: data = {"items": [], "total": 0}
            route.fulfill(status=200, content_type="application/json", body=json.dumps(data))
        page.route('**/api/v1/**', mock)
        page.goto(ORIGIN + '/dashboard/')
        search = page.get_by_placeholder('Search by name or email')
        search.fill('John')
        page.get_by_label('Enrollment status').select_option('true')
        page.get_by_role('link', name='John Doe').click()
        expect(page).to_have_url(__import__('re').compile(r'/students/s1/attendance'))
        expect(page.get_by_role('heading', name='John Doe')).to_be_visible()
        expect(page.get_by_label('Student attendance course')).to_have_value('c')
        expect(page.get_by_text('92%', exact=True)).to_be_visible()
        output = Path(os.getenv('TEMP', '.')) / 'student-attendance-preview'
        output.mkdir(exist_ok=True)
        page.screenshot(path=str(output / 'desktop.png'), full_page=True)
        page.get_by_label('Student attendance course').select_option('b')
        expect(page.get_by_text('50%', exact=True)).to_be_visible()
        expect(page.get_by_text('No recent check-ins.', exact=True)).to_be_visible()
        page.reload()
        expect(page.get_by_role('heading', name='John Doe')).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'page overflows on mobile'
        scroll = page.locator('table').locator('..')
        assert scroll.evaluate('(el) => el.scrollWidth > el.clientWidth'), 'table must scroll within its container'
        page.screenshot(path=str(output / 'mobile.png'), full_page=True)
        page.get_by_role('link', name='Back to Enrollments', exact=False).click()
        expect(page.get_by_placeholder('Search by name or email')).to_have_value('John')
        expect(page.get_by_label('Enrollment status')).to_have_value('true')
        expect(page.get_by_label('Enrollment course')).to_have_value('c')
        assert not errors, errors
        browser.close()
        print('PASS: roster link, course switching, refresh, desktop/mobile layout, and restored roster filters.')
        print('Screenshots:', output)

if __name__ == '__main__':
    main()
