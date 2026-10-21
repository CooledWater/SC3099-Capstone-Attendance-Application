"""Exercise the real dashboard in installed headless Edge using CDP.

Uses websockets/httpx from the backend test environment; all API data is mocked.
Run after the dashboard build: python new-tests/browser_enrollments.py
"""
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

import httpx
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
EDGE = os.environ.get("ENROLLMENTS_BROWSER", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class Browser:
    def __init__(self, ws):
        self.ws = ws
        self.sequence = 0
        self.requests = []
        self.students = [dict(id="enrollment-alice", student_id="alice", student_name="Alice Tan", student_email="alice@example.edu", is_active=True),
                         dict(id="enrollment-bob", student_id="bob", student_name="Bob Lee", student_email="bob@example.edu", is_active=False)]
        self.duplicate = True
        self.delayed = []
        self.no_courses = False
        self.roster_error = False

    def command(self, method, params=None):
        ready = [item for item in self.delayed if item[0] <= time.monotonic()]
        self.delayed = [item for item in self.delayed if item[0] > time.monotonic()]
        for _, event in ready:
            event["released"] = True
            self.route(event)
        self.sequence += 1
        request_id = self.sequence
        self.ws.send(json.dumps(dict(id=request_id, method=method, params=params or {})))
        while True:
            message = json.loads(self.ws.recv(timeout=15))
            if message.get("method") == "Fetch.requestPaused":
                self.route(message["params"])
            elif message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})

    def route(self, event):
        from urllib.parse import urlparse, parse_qs
        request = event["request"]
        url = urlparse(request["url"])
        query = parse_qs(url.query)
        path = url.path
        method = request["method"]
        self.requests.append((method, path, query, request.get("postData")))
        code, body = 200, {}
        if method == "OPTIONS":
            code, body = 204, None
        elif path.endswith("/auth/dashboard/refresh"):
            body = {"access_token": "test-token"}
        elif path.endswith("/users/me"):
            body = dict(id="teacher", full_name="Test Teacher", role="instructor", email="teacher@example.edu")
        elif path.endswith("/courses/"):
            courses = [dict(id="course-a", code="SC4000", name="Machine Learning", instructor_id="teacher")]
            courses += [dict(id=f"other-{i}", code=f"OTHER{i}", name="Other", instructor_id="other") for i in range(99)]
            courses += [dict(id="course-b", code="SC3099", name="Capstone", instructor_id="teacher")]
            offset = int(query.get("offset", [0])[0])
            body = {"items": [], "total": 0} if self.no_courses else {"items": courses[offset:offset + 100], "total": 101}
        elif "/enrollments/course/" in path:
            if query.get("search") == ["slow"] and not event.get("released"):
                self.delayed.append((time.monotonic() + 0.6, event))
                return
            source = self.students if path.endswith("course-a") else [dict(id="enrollment-carol", student_id="carol", student_name="Carol Lim", student_email="carol@example.edu", is_active=True)]
            search = query.get("search", [""])[0].lower()
            status = query.get("is_active", ["true"])[0]
            rows = [row for row in source if (status == "all" or row["is_active"] == (status == "true")) and search in (row["student_name"] + row["student_email"]).lower()]
            body = dict(course_id=path.rsplit("/", 1)[-1], course_code="SC4000", total_records=len(source), total_enrolled=sum(row["is_active"] for row in source), active_count=sum(row["is_active"] for row in source), inactive_count=sum(not row["is_active"] for row in source), matching_count=len(rows), students=rows)
            if self.roster_error:
                code, body = 403, {"detail": "No roster access"}
        elif path.endswith("/enrollments/") and method == "POST":
            if self.duplicate:
                code, body = 400, {"detail": "Student already enrolled"}
                self.duplicate = False
            else:
                self.students.append(dict(id="enrollment-new", student_id="new", student_name="New Student", student_email="new@example.edu", is_active=True))
                code, body = 201, {"id": "enrollment-new"}
        elif path.endswith("/enrollments/bulk"):
            payload = json.loads(request["postData"])
            assert payload["create_accounts"] is False
            assert payload["student_emails"] == ["grace@example.edu", "missing@example.edu"]
            body = dict(enrolled=1, created=0, already_enrolled=0, not_found=1, details=[dict(email="grace@example.edu", status="enrolled"), dict(email="missing@example.edu", status="not_found")])
        elif "/enrollments/" in path and method == "DELETE":
            assert path.endswith("enrollment-alice"), "Must delete by enrollment ID"
            self.students[0]["is_active"] = False
            code, body = 204, None
        elif path.endswith("/sessions/"):
            body = {"items": [], "total": 0}
        self.sequence += 1
        params = dict(requestId=event["requestId"], responseCode=code,
                      responseHeaders=[dict(name="Content-Type", value="application/json"), dict(name="Access-Control-Allow-Origin", value=request["headers"].get("Origin", request["headers"].get("origin", ""))), dict(name="Access-Control-Allow-Credentials", value="true"), dict(name="Access-Control-Allow-Headers", value="authorization,content-type,accept"), dict(name="Access-Control-Allow-Methods", value="GET,POST,DELETE,OPTIONS")],
                      body=base64.b64encode(json.dumps(body).encode() if body is not None else b"").decode())
        self.ws.send(json.dumps(dict(id=self.sequence, method="Fetch.fulfillRequest", params=params)))

    def evaluate(self, expression):
        result = self.command("Runtime.evaluate", dict(expression=expression, returnByValue=True))
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def wait(self, expression):
        for _ in range(250):
            if self.evaluate(expression):
                return
            time.sleep(0.05)
        raise AssertionError(expression + "\n" + self.evaluate("document.body.innerText"))

    def click(self, text):
        self.wait(f"Array.from(document.querySelectorAll('button')).some(e => e.textContent.trim() === {json.dumps(text)} && !e.disabled)")
        self.evaluate(f"Array.from(document.querySelectorAll('button')).find(e => e.textContent.trim() === {json.dumps(text)}).click()")

    def fill(self, selector, value):
        self.evaluate(f"(() => {{const e=document.querySelector({json.dumps(selector)}); const p=e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(p,'value').set.call(e,{json.dumps(value)}); e.dispatchEvent(new Event('input',{{bubbles:true}}));}})()")

    def select(self, selector, value):
        self.evaluate(f"(() => {{const e=document.querySelector({json.dumps(selector)}); e.value={json.dumps(value)}; e.dispatchEvent(new Event('change',{{bubbles:true}}));}})()")


def run_dashboard_checks():
    with tempfile.TemporaryDirectory(prefix="enrollment-browser-", ignore_cleanup_errors=True) as temporary:
        web_port, debug_port = port(), port()
        hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with tempfile.TemporaryFile() as log:
            server = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1", "--port", str(web_port)], cwd=ROOT / "module4-observability", stdout=log, stderr=log, creationflags=hidden)
            browser = None
            try:
                for _ in range(100):
                    try:
                        if httpx.get(f"http://127.0.0.1:{web_port}").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.1)
                browser = subprocess.Popen([EDGE, "--headless=new", "--no-first-run", "--no-default-browser-check", f"--user-data-dir={temporary}", f"--remote-debugging-port={debug_port}", "about:blank"], stdout=log, stderr=log, creationflags=hidden)
                for _ in range(100):
                    try:
                        pages = httpx.get(f"http://127.0.0.1:{debug_port}/json/list").json()
                        page = next(page for page in pages if page["type"] == "page")
                        break
                    except (httpx.TransportError, StopIteration):
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Headless browser did not start")
                with connect(page["webSocketDebuggerUrl"], max_size=8_000_000) as socket:
                    ui = Browser(socket)
                    ui.command("Fetch.enable", {"patterns": [{"urlPattern": "*api/v1/*"}]})
                    ui.command("Page.navigate", {"url": f"http://127.0.0.1:{web_port}"})
                    ui.wait("document.body.innerText.includes('Enrollments')")
                    ui.click("Enrollments")
                    ui.wait("document.body.innerText.includes('Alice Tan')")
                    assert ui.evaluate("document.querySelector('[aria-label=\"Enrollment course\"]').options.length") == 2
                    ui.fill("input[placeholder='Search by name or email']", "Bob")
                    ui.wait("document.body.innerText.includes('Bob Lee') && !document.body.innerText.includes('Alice Tan')")
                    ui.fill("input[placeholder='Search by name or email']", "")
                    ui.wait("document.body.innerText.includes('Alice Tan')")
                    ui.select("select:not([aria-label])", "false")
                    ui.wait("!document.body.innerText.includes('Alice Tan') && document.body.innerText.includes('Bob Lee')")
                    ui.select("select:not([aria-label])", "all")
                    ui.wait("document.body.innerText.includes('Alice Tan')")
                    ui.fill("input[placeholder='Search by name or email']", "slow")
                    ui.wait("document.body.innerText.includes('No students match these filters.')")
                    assert not any(query.get("search") == ["slow"] for _, _, query, _ in ui.requests)
                    assert all(query.get('is_active') == ['all'] and query.get('search', ['']) == ['']
                               for _, path, query, _ in ui.requests
                               if '/enrollments/course/' in path and not path.endswith('/invitations'))
                    assert not ui.evaluate("document.body.innerText.includes('Loading roster...')")
                    ui.select("[aria-label='Enrollment course']", "course-b")
                    ui.wait("document.body.innerText.includes('Carol Lim') && !document.body.innerText.includes('Alice Tan')")
                    time.sleep(0.7)
                    ui.evaluate("true")
                    assert ui.evaluate("document.body.innerText.includes('Carol Lim')"), "Stale response replaced the selected course"
                    ui.select("[aria-label='Enrollment course']", "course-a")
                    ui.wait("document.body.innerText.includes('Alice Tan')")
                    ui.fill("input[placeholder='Search by name or email']", "not-a-student")
                    ui.wait("document.body.innerText.includes('No students match these filters.')")
                    ui.fill("input[placeholder='Search by name or email']", "")
                    ui.wait("document.body.innerText.includes('Alice Tan')")
                    ui.click("+ Add students")
                    ui.wait("document.querySelector('[role=dialog]') !== null")
                    ui.fill("[role=dialog] input:not([type=checkbox])", "student-id")
                    ui.click("Enroll student")
                    ui.wait("document.body.innerText.includes('Student already enrolled')")
                    ui.click("Enroll student")
                    ui.wait("document.body.innerText.includes('Student enrolled successfully.')")
                    ui.click("Bulk enrollment")
                    ui.wait("document.querySelector('textarea') !== null")
                    ui.fill("textarea", "bad-email")
                    ui.wait("document.body.innerText.includes('Invalid addresses:')")
                    assert ui.evaluate("Array.from(document.querySelectorAll('button')).find(e => e.textContent==='Enroll students').disabled")
                    ui.fill("textarea", "grace@example.edu,missing@example.edu\ngrace@example.edu")
                    ui.wait("document.body.innerText.includes('2 unique addresses')")
                    ui.click("Enroll students")
                    ui.wait("document.body.innerText.includes('1 unresolved')")
                    assert ui.evaluate("document.querySelector('textarea').value") == "missing@example.edu"
                    ui.click("Close")
                    ui.wait("document.querySelector('[role=dialog]') === null")
                    ui.click("Remove")
                    ui.wait("document.querySelector('[role=alertdialog]') !== null")
                    ui.evaluate("Array.from(document.querySelectorAll('[role=alertdialog] button')).find(e=>e.textContent==='Remove').click()")
                    ui.wait("document.querySelector('[role=alertdialog]') === null")
                    assert any(method == "DELETE" and path.endswith("enrollment-alice") for method, path, *_ in ui.requests)
                    ui.roster_error = True
                    ui.select("[aria-label='Enrollment course']", "course-b")
                    ui.wait("document.body.innerText.includes('No roster access')")
                    ui.select("[aria-label='Enrollment course']", "course-a")
                    ui.select("select:not([aria-label])", "true")
                    ui.wait("document.body.innerText.includes('No roster access')")
                    ui.roster_error = False
                    ui.click("Retry")
                    ui.wait("document.body.innerText.includes('New Student')")
                    ui.command("Emulation.setDeviceMetricsOverride", dict(width=390, height=844, deviceScaleFactor=1, mobile=True))
                    assert ui.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "Page overflows mobile viewport"
                    ui.no_courses = True
                    ui.command("Page.reload")
                    ui.wait("document.querySelector('[aria-label=\"Enrollment course\"]') === null")
                    ui.wait("document.body.innerText.includes('Enrollments')")
                    ui.click("Enrollments")
                    ui.wait("document.body.innerText.includes('No courses are assigned to your account.')")
                    try:
                        ui.command("Browser.close")
                    except Exception:
                        pass
                    print("PASS: scoped/paginated courses, instant local search/status filtering without search requests, course switching, single errors/success, bulk validation/results/retry, deletion by enrollment ID, mobile overflow, empty-course and no-result states, roster errors/retry")
            finally:
                if browser:
                    browser.terminate()
                    browser.wait(timeout=15)
                server.terminate()
                server.wait(timeout=15)


if __name__ == "__main__":
    run_dashboard_checks()
