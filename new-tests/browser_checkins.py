"""Headless Edge checks of built dashboard; API responses are all local mocks."""
import base64
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import httpx
from websockets.sync.client import connect
from browser_enrollments import Browser, EDGE, ROOT, port


class CheckinsBrowser(Browser):
    def __init__(self, ws):
        super().__init__(ws)
        self.statuses = ["approved", "flagged", "appealed", "pending", "rejected", "approved"]
        self.fail_review = False
        self.exported = False
        self.slow = False

    def roster(self, course="course-a", meeting="meeting-a"):
        rows = []
        for i in range(18 if course == "course-a" else 1):
            rows.append(dict(student_id=f"s{i}", student_name=(f"Student {i}" if course == "course-a" else "Other Course Student"), student_email=f"s{i}@example.edu", checkin_id=f"c{i}" if i < 6 else None,
                             checked_in_at=f"2026-10-16T09:{i:02}:00Z" if i < 6 else None,
                             attendance="present" if i < 6 else "absent",
                             status=self.statuses[i] if i < 6 else None))
        return dict(session_id=meeting, course_id=course, session_status="closed", expected=len(rows), items=rows,
                    summary=dict(present=6, absent=12, attendance_rate=6/18,
                                 verification={status: self.statuses.count(status) for status in ("approved", "flagged", "appealed", "pending", "rejected")}))

    def route(self, event):
        request = event["request"]
        url = urlparse(request["url"])
        path, query, method = url.path, parse_qs(url.query), request["method"]
        self.requests.append((method, path, query, request.get("postData")))
        code, body, content_type = 200, {}, "application/json"
        if path.endswith("/auth/dashboard/refresh"):
            body = {"access_token": "test-token"}
        elif path.endswith("/users/me"):
            body = dict(id="teacher", role="instructor", full_name="Teacher", email="teacher@example.edu")
        elif path.endswith("/courses/"):
            body = {"items": [dict(id=f"course-{suffix}", code=code, name=name, instructor_id="teacher") for suffix, code, name in [("a", "SC4000", "Machine Learning"), ("b", "SC3099", "Capstone")]], "total": 2}
        elif path.endswith("/sessions/"):
            course = query.get("course_id", ["course-a"])[0]
            suffix = "b" if course == "course-b" else "a"
            body = {"items": [dict(id=f"meeting-{suffix}", course_id=course, name=f"Lecture {suffix.upper()}", scheduled_start="2026-10-16T09:00:00Z", scheduled_end="2026-10-16T10:00:00Z", checkin_opens_at="2026-10-16T08:45:00Z", checkin_closes_at="2026-10-16T09:15:00Z", status="closed")], "total": 1}
            body["items"].append(dict(body["items"][0], id=f"older-{suffix}", name="Older session", scheduled_start="2026-10-15T09:00:00Z"))
            body["total"] = 2
        elif path.endswith("/attendance"):
            if self.slow and "meeting-a" in path and not event.get("released"):
                self.delayed.append((time.monotonic() + 0.8, event))
                self.slow = False
                return
            course = "course-b" if "meeting-b" in path else "course-a"
            body = self.roster(course, path.split("/")[-2])
        elif path.endswith("/checkins/flagged"):
            rows = [dict(id=f"c{i}", session_id="meeting-a", status=status) for i, status in enumerate(self.statuses) if status in ("flagged", "appealed")]
            # Deliberately paginate despite requested limit to exercise all pages.
            offset = int(query.get("offset", [0])[0])
            body = {"items": rows[offset:offset + 1], "total": len(rows)}
        elif path.endswith("/review"):
            index = int(path.split("/")[-2][1:])
            payload = json.loads(request["postData"])
            assert payload["status"] in ("approved", "rejected")
            if self.fail_review:
                code, body = 503, {"detail": "Review failed; please retry"}
            else:
                self.statuses[index] = payload["status"]
                body = {"id": f"c{index}", "status": payload["status"]}
        elif "/checkins/c" in path:
            index = int(path.rsplit("/", 1)[-1][1:])
            body = dict(id=f"c{index}", session_id="meeting-a", course_id="course-a", student_id=f"s{index}", status=self.statuses[index], risk_score=0.78431,
                        risk_factors=[dict(type="geo_out_of_bounds", severity="high", weight=0.4), dict(type="device_unknown", severity="medium", weight=0.15)],
                        checked_in_at=f"2026-10-16T09:{index:02}:00Z", appeal_reason="GPS inaccurate" if index == 2 else None)
        elif "/export/session/" in path:
            assert path.endswith("meeting-a") and query.get("format") == ["csv"]
            self.exported = True
            content_type, body = "text/csv", "student_name,status\nStudent 0,approved\n"
        elif "/enrollments/course/" in path:
            body = dict(course_id="course-b", course_code="SC3099", total_records=0, total_enrolled=0, active_count=0, inactive_count=0, students=[])
        elif path.endswith("/checkins/"):
            body = {"items": [], "total": 0}
        self.sequence += 1
        headers = [{"name": "Content-Type", "value": content_type}]
        if content_type == "text/csv":
            headers.append({"name": "Content-Disposition", "value": 'attachment; filename="session.csv"'})
        encoded = json.dumps(body).encode() if content_type == "application/json" else body.encode()
        self.ws.send(json.dumps(dict(id=self.sequence, method="Fetch.fulfillRequest", params=dict(requestId=event["requestId"], responseCode=code, responseHeaders=headers, body=base64.b64encode(encoded).decode()))))


def run():
    with tempfile.TemporaryDirectory(prefix="checkins-browser-", ignore_cleanup_errors=True) as temporary, tempfile.TemporaryFile() as log:
        web_port, debug_port = port(), port()
        hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        server = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1", "--port", str(web_port)], cwd=ROOT / "module4-observability", stdout=log, stderr=log, creationflags=hidden)
        browser = None
        try:
            for _ in range(100):
                try:
                    if httpx.get(f"http://127.0.0.1:{web_port}/dashboard/").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            browser = subprocess.Popen([EDGE, "--headless=new", "--no-first-run", "--no-default-browser-check", f"--user-data-dir={temporary}", f"--remote-debugging-port={debug_port}", "about:blank"], stdout=log, stderr=log, creationflags=hidden)
            for _ in range(100):
                try:
                    page = next(page for page in httpx.get(f"http://127.0.0.1:{debug_port}/json/list").json() if page["type"] == "page")
                    break
                except (httpx.TransportError, StopIteration):
                    time.sleep(0.1)
            else:
                raise RuntimeError("Headless Edge did not start")
            with connect(page["webSocketDebuggerUrl"], max_size=8_000_000) as ws:
                ui = CheckinsBrowser(ws)
                ui.command("Emulation.setDeviceMetricsOverride", dict(width=1280, height=1000, deviceScaleFactor=1, mobile=False))
                ui.command("Fetch.enable", {"patterns": [{"urlPattern": "*api/v1/*"}]})
                ui.command("Page.navigate", {"url": f"http://127.0.0.1:{web_port}/dashboard/"})
                ui.click("Sessions")
                ui.wait("document.querySelector('[aria-label=\"View check-ins for Older session\"]') !== null")
                ui.evaluate("document.querySelector('[aria-label=\"View check-ins for Older session\"]').click()")
                ui.wait("document.querySelector('[aria-label=\"Check-ins session\"]')?.value === 'older-a'")
                assert ui.evaluate("!document.body.innerText.includes('No check-ins for this session.')")
                ui.select("[aria-label='Check-ins session']", "meeting-a")
                ui.wait("document.body.innerText.includes('18 expected')")
                assert ui.evaluate("document.querySelector('thead').innerText.includes('Check-in') && !document.querySelector('thead').innerText.includes('(SGT)')")
                assert ui.evaluate("document.body.innerText.includes('Present') && !document.body.innerText.includes('On time') && !document.body.innerText.includes('Session export contains')")
                assert ui.evaluate("document.querySelector('[aria-label=\"Check-ins course\"]').options.length") == 2
                assert ui.evaluate("document.querySelector('tbody tr').innerText.includes('Student 5')"), "Default order is latest check-in first"
                ui.click("Next")
                ui.wait("document.body.innerText.includes('11–18 of 18 students')")
                assert ui.evaluate("document.body.innerText.includes('18 expected')")
                ui.click("Flagged check-ins")
                ui.wait("document.body.innerText.includes('1–2 of 2 students')")
                assert ui.evaluate("document.querySelector('tbody').querySelectorAll('button').length") == 2
                ui.click("Review")
                ui.wait("document.body.innerText.includes('Risk factors') && !document.body.innerText.includes('Loading full check-in')")
                assert ui.evaluate("document.body.innerText.includes('0.78431') && document.body.innerText.includes('GPS inaccurate')")
                assert ui.evaluate("getComputedStyle(Array.from(document.querySelectorAll('button')).find(e => e.textContent==='Approve')).backgroundColor.includes('oklch')")
                ui.fill("textarea", "Evidence checked")
                ui.click("Approve")
                ui.wait("document.body.innerText.includes('Check-in approved.') && document.body.innerText.includes('1–1 of 1 students')")
                assert ui.evaluate("!document.querySelector('textarea') && !document.body.innerText.includes('Student explanation')")
                assert ui.evaluate("!document.body.innerText.includes('Risk factors')")
                ui.click("Close")
                ui.click("Review")
                ui.wait("document.querySelector('textarea') !== null")
                ui.fail_review = True
                ui.fill("textarea", "Retain these notes")
                ui.click("Reject")
                ui.wait("document.body.innerText.includes('Review failed; please retry')")
                assert ui.evaluate("document.querySelector('textarea').value") == "Retain these notes"
                ui.fail_review = False
                ui.click("Reject")
                ui.wait("document.body.innerText.includes('Check-in rejected.') && document.body.innerText.includes('0–0 of 0 students')")
                ui.click("Close")
                ui.click("Clear all")
                ui.fill("input[aria-label='Search student name or email']", "s17@example")
                ui.wait("document.body.innerText.includes('1–1 of 1 students')")
                assert ui.evaluate("document.querySelector('tbody').innerText.includes('Absent') && document.querySelector('tbody').innerText.includes('No check-in')")
                ui.click("Export CSV")
                ui.wait("!document.body.innerText.includes('Exporting…')")
                assert ui.exported
                ui.fill("input[aria-label='Search student name or email']", "")
                ui.command("Emulation.setDeviceMetricsOverride", dict(width=390, height=844, deviceScaleFactor=1, mobile=True))
                assert ui.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "Mobile page overflow"
                screenshot = ui.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
                output = Path(tempfile.gettempdir()) / "saiv-checkins-mobile.png"
                output.write_bytes(base64.b64decode(screenshot["data"]))
                # Preserve course selection across tabs, then ignore late old-course results.
                ui.select("[aria-label='Check-ins course']", "course-b")
                ui.wait("document.body.innerText.includes('Other Course Student')")
                ui.click("Enrollments")
                ui.wait("document.querySelector('[aria-label=\"Enrollment course\"]') !== null")
                assert ui.evaluate("document.querySelector('[aria-label=\"Enrollment course\"]').value") == "course-b"
                ui.click("Check-ins")
                ui.wait("document.querySelector('[aria-label=\"Check-ins course\"]') !== null")
                assert ui.evaluate("document.querySelector('[aria-label=\"Check-ins course\"]').value") == "course-b"
                ui.slow = True
                ui.select("[aria-label='Check-ins course']", "course-a")
                ui.wait("document.querySelector('[aria-label=\"Check-ins session\"]').value === 'meeting-a'")
                ui.select("[aria-label='Check-ins course']", "course-b")
                ui.wait("document.body.innerText.includes('Other Course Student')")
                time.sleep(1)
                ui.evaluate("true")
                assert ui.evaluate("document.body.innerText.includes('Other Course Student') && !document.querySelector('[aria-label=\"Check-in details\"]')")
                print("PASS: latest-first roster, pagination, whole-session totals, paginated flagged filter, risk evidence, approval/rejection, failed notes retention, scoped export, mobile overflow, shared course selection and stale-response isolation")
                print("Screenshot:", output)
        finally:
            if browser:
                browser.terminate()
                browser.wait(timeout=15)
            server.terminate()
            server.wait(timeout=15)


if __name__ == "__main__":
    run()
