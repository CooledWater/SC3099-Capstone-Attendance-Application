"""Calendar UI regression using installed headless Edge and local mocked APIs."""
import base64
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import httpx
from websockets.sync.client import connect
from browser_enrollments import Browser, EDGE, ROOT, port

SGT = timezone(timedelta(hours=8))
now = datetime.now(SGT)
MONDAY = (now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())) + timedelta(days=7)
def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class CalendarBrowser(Browser):
    def __init__(self, ws):
        super().__init__(ws)
        self.items = {}
        for id, name, hour, minute, status, day in [
            ("move", "Reschedule me", 10, 0, "scheduled", 0),
            ("active", "Live lecture", 10, 15, "active", 0),
            ("weekend", "Saturday lab", 10, 0, "scheduled", 5),
            ("closed", "Closed history", 14, 0, "closed", 0),
            ("cancelled", "Cancelled history", 16, 0, "cancelled", 0),
        ]:
            start = MONDAY + timedelta(days=day, hours=hour, minutes=minute)
            self.items[id] = dict(id=id, name=name, course_id="course-a", instructor_id="teacher", status=status,
                                  scheduled_start=iso(start), scheduled_end=iso(start + timedelta(hours=1)),
                                  checkin_opens_at=iso(start), checkin_closes_at=iso(start + timedelta(hours=1)),
                                  course_code="SC4000", course_name="Machine Learning", venue_name="LT26", total_enrolled=3, geofence_radius_meters=100)
        self.fail_move = False
        self.stale_move = False
        self.patches = []

    def route(self, event):
        request = event["request"]
        url = urlparse(request["url"]); path = url.path; query = parse_qs(url.query); method = request["method"]
        self.requests.append((method, path, query, request.get("postData")))
        code, body = 200, {}
        if path.endswith("/auth/dashboard/refresh"):
            body = {"access_token": "mock-token"}
        elif path.endswith("/users/me"):
            body = dict(id="teacher", role="instructor", full_name="Teacher", email="teacher@example.edu")
        elif path.endswith("/courses/"):
            body = {"items": [dict(id="course-a", code="SC4000", name="Machine Learning", instructor_id="teacher"), dict(id="course-b", code="SC3000", name="Tutorials", instructor_id="teacher")], "total": 2}
        elif path.endswith("/sessions/") and method == "POST":
            value = json.loads(request["postData"]); value.update(id="created", instructor_id="teacher", status="scheduled", course_code="SC4000", course_name="Machine Learning")
            self.items["created"] = value; code, body = 201, value
        elif path.endswith("/sessions/"):
            rows = list(self.items.values())
            if "course_id" in query: rows = [row for row in rows if row["course_id"] == query["course_id"][0]]
            if "status" in query: rows = [row for row in rows if row["status"] == query["status"][0]]
            if "end_date" in query: rows = [row for row in rows if datetime.fromisoformat(row["scheduled_start"].replace("Z", "+00:00")) <= datetime.fromisoformat(query["end_date"][0].replace("Z", "+00:00"))]
            offset = int(query.get("offset", [0])[0])
            body = {"items": rows[offset:offset + 2], "total": len(rows)}
        elif "/sessions/" in path:
            id = path.rsplit("/", 1)[-1]
            if id not in self.items: code, body = 404, {"detail": "Session not found"}
            elif method == "DELETE":
                self.items.pop(id); code = 204
            elif method == "PATCH":
                payload = json.loads(request["postData"])
                if "scheduled_start" in payload and self.fail_move:
                    code, body = 503, {"detail": "Move failed; original position preserved"}
                else:
                    self.patches.append((id, payload)); self.items[id].update(payload); body = self.items[id]
            else:
                if self.stale_move and id == "move": self.items[id]["status"] = "active"
                body = self.items[id]
        elif path.endswith("/checkins/"):
            body = {"items": [], "total": 0}
        elif "/enrollments/course/" in path:
            body = {"total_enrolled": 3}
        self.sequence += 1
        self.ws.send(json.dumps(dict(id=self.sequence, method="Fetch.fulfillRequest", params=dict(requestId=event["requestId"], responseCode=code,
                            responseHeaders=[dict(name="Content-Type", value="application/json")], body=base64.b64encode(json.dumps(body).encode() if code != 204 else b"").decode()))))

    def drag(self, id, instant):
        self.evaluate("""(() => {const data=new DataTransfer(); const source=document.querySelector('[data-session-id="%s"]'); const slot=document.querySelector('[data-calendar-slot="%s"]'); source.dispatchEvent(new DragEvent('dragstart',{bubbles:true,dataTransfer:data})); slot.dispatchEvent(new DragEvent('dragover',{bubbles:true,dataTransfer:data})); slot.dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:data}));})()""" % (id, instant))

    def menu(self, name):
        self.evaluate("""(() => {const e=document.querySelector('[aria-label="More actions for %s"]'); e.focus(); e.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true}));})()""" % name)


def run():
    with tempfile.TemporaryDirectory(prefix="calendar-browser-", ignore_cleanup_errors=True) as temporary, tempfile.TemporaryFile() as log:
        web_port, debug_port = port(), port(); hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        server = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1", "--port", str(web_port)], cwd=ROOT / "module4-observability", stdout=log, stderr=log, creationflags=hidden)
        browser = None
        try:
            for _ in range(100):
                try:
                    if httpx.get(f"http://127.0.0.1:{web_port}/dashboard/").status_code == 200: break
                except httpx.TransportError: pass
                time.sleep(0.1)
            browser = subprocess.Popen([EDGE, "--headless=new", "--no-first-run", "--no-default-browser-check", f"--user-data-dir={temporary}", f"--remote-debugging-port={debug_port}", "about:blank"], stdout=log, stderr=log, creationflags=hidden)
            for _ in range(100):
                try:
                    page = next(page for page in httpx.get(f"http://127.0.0.1:{debug_port}/json/list").json() if page["type"] == "page"); break
                except (httpx.TransportError, StopIteration): time.sleep(0.1)
            else: raise RuntimeError("Edge did not start")
            with connect(page["webSocketDebuggerUrl"], max_size=8_000_000) as ws:
                ui = CalendarBrowser(ws)
                ui.command("Emulation.setDeviceMetricsOverride", dict(width=1440, height=1100, deviceScaleFactor=1, mobile=False))
                ui.command("Fetch.enable", {"patterns": [{"urlPattern": "*api/v1/*"}]})
                ui.command("Page.navigate", {"url": f"http://127.0.0.1:{web_port}/dashboard/"})
                ui.click("Sessions"); ui.click("Calendar")
                assert ui.evaluate("!document.body.innerText.includes('Week view') && !document.body.innerText.includes('Scheduled and Active sessions · Singapore time') && !document.body.innerText.includes('Scheduled · draggable')")
                ui.wait("document.body.innerText.includes('No Scheduled or Active sessions this week')")
                ui.evaluate("document.querySelector('[aria-label=\"Next week\"]').click()")
                ui.wait("document.querySelector('[data-session-id=\"move\"]') !== null")
                assert not ui.evaluate("document.querySelector('[data-session-id=\"closed\"]') !== null")
                assert not ui.evaluate("document.querySelector('[data-session-id=\"weekend\"]') !== null")
                assert ui.evaluate("document.querySelector('[data-session-id=\"move\"]').getBoundingClientRect().right <= document.querySelector('[data-session-id=\"active\"]').getBoundingClientRect().left + 5")
                ui.evaluate("document.querySelector('[data-session-id=\"active\"]').click()")
                ui.wait("document.body.innerText.includes('Active session details')")
                assert ui.evaluate("document.querySelector('#edit-session-form input[type=\"datetime-local\"]').matches(':disabled')")
                assert not ui.evaluate("document.querySelector('[data-session-id=\"active\"]').draggable")
                ui.click("Cancel")
                original = ui.items["move"]["scheduled_start"]
                proposed = iso(MONDAY + timedelta(days=1, hours=14)).replace("Z", ".000Z")
                ui.drag("move", proposed); ui.wait("document.body.innerText.includes('Move session?')")
                ui.click("Cancel"); assert ui.items["move"]["scheduled_start"] == original and not ui.patches
                ui.fail_move = True
                ui.drag("move", proposed); ui.click("Confirm move")
                ui.wait("document.body.innerText.includes('Move failed; original position preserved')")
                assert ui.items["move"]["scheduled_start"] == original
                ui.click("Cancel"); ui.fail_move = False
                ui.drag("move", proposed); ui.click("Confirm move")
                ui.wait("document.querySelector('[role=\"alertdialog\"]') === null")
                assert ui.items["move"]["scheduled_start"] == proposed
                assert datetime.fromisoformat(ui.items["move"]["scheduled_end"].replace("Z", "+00:00")) - datetime.fromisoformat(proposed.replace("Z", "+00:00")) == timedelta(hours=1)
                ui.click("List"); ui.wait("document.body.innerText.includes('2:00 PM') || document.body.innerText.includes('2:00 pm')")
                ui.click("Calendar"); ui.wait("document.querySelector('[data-session-id=\"move\"]') !== null")
                create_time = iso(MONDAY + timedelta(days=2, hours=12)).replace("Z", ".000Z")
                ui.evaluate(f"document.querySelector('[data-calendar-slot=\"{create_time}\"]').click()")
                ui.wait("document.querySelector('form input[type=\"datetime-local\"]') !== null")
                assert ui.evaluate("document.querySelector('form input[type=\"datetime-local\"]').value").endswith("T12:00")
                assert ui.evaluate("Array.from(document.querySelectorAll('form label')).some(e=>e.innerText.trim().startsWith('Venue')) && !Array.from(document.querySelectorAll('form label')).some(e=>/Geofence latitude|Geofence longitude/.test(e.innerText))")
                ui.fill("input[placeholder='Lecture Hall B']", "New venue")
                ui.click("Create session"); ui.wait("document.querySelector('[data-session-id=\"created\"]') !== null")
                create_payload = json.loads(next(data for method, path, _, data in reversed(ui.requests) if method == "POST" and path.endswith("/sessions/")))
                assert "venue_latitude" not in create_payload and "venue_longitude" not in create_payload
                ui.evaluate("document.querySelector('[data-session-id=\"created\"]').click()")
                ui.wait("document.body.innerText.includes('Edit scheduled session')")
                assert ui.evaluate("Array.from(document.querySelectorAll('[role=dialog] label')).some(e=>e.innerText.trim().startsWith('Venue')) && !Array.from(document.querySelectorAll('[role=dialog] label')).some(e=>/Geofence latitude|Geofence longitude/.test(e.innerText))")
                assert ui.evaluate("!Array.from(document.querySelectorAll('[role=dialog] button')).some(e=>['Activate','Delete'].includes(e.textContent.trim()))")
                ui.click("Cancel"); ui.click("List")
                ui.menu("Live lecture"); ui.wait("document.querySelector('[role=menu]') !== null")
                ui.evaluate("Array.from(document.querySelectorAll('[role=menuitem]')).find(e=>e.textContent.includes('Close session')).click()")
                ui.wait("!document.body.innerText.includes('Closing…')")
                ui.menu("New venue session"); ui.wait("document.querySelector('[role=menu]') !== null")
                ui.evaluate("Array.from(document.querySelectorAll('[role=menuitem]')).find(e=>e.textContent==='Delete').click()")
                ui.click("Confirm"); ui.wait("document.querySelector('[role=alertdialog]') === null")
                ui.click("Calendar"); ui.wait("document.querySelector('[data-session-id=\"weekend\"]') === null && document.querySelector('[data-session-id=\"active\"]') === null")
                patches = len(ui.patches); ui.stale_move = True
                ui.drag("move", iso(MONDAY + timedelta(days=2, hours=10)).replace("Z", ".000Z"))
                ui.click("Confirm move"); ui.wait("document.body.innerText.includes('no longer Scheduled')")
                assert len(ui.patches) == patches
                ui.click("Cancel")
                ui.wait("document.querySelector('[data-session-id=\"move\"]')?.draggable === false")
                ui.select("select", "course-b")
                ui.wait("document.body.innerText.includes('No Scheduled or Active sessions this week')")
                assert not ui.evaluate("document.querySelector('[data-session-id=\"move\"]') !== null")
                ui.select("select", "course-a")
                ui.wait("document.querySelector('[data-session-id=\"move\"]') !== null")
                ui.evaluate("document.querySelector('[data-session-id=\"move\"]').click()")
                ui.click("Cancel session")
                ui.wait("document.querySelector('[data-session-id=\"move\"]') === null")
                assert ui.items["move"]["status"] == "cancelled"
                screenshot = ui.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
                (Path(tempfile.gettempdir()) / "saiv-calendar-desktop.png").write_bytes(base64.b64decode(screenshot["data"]))
                ui.command("Emulation.setDeviceMetricsOverride", dict(width=390, height=844, deviceScaleFactor=1, mobile=True))
                assert ui.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "Mobile overflow"
                screenshot = ui.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
                (Path(tempfile.gettempdir()) / "saiv-calendar-mobile.png").write_bytes(base64.b64decode(screenshot["data"]))
                print("PASS: complete week loading, active/scheduled only, weekend/overlap layout, active locks, drag cancellation/failure/success, duration preservation, list consistency, click create, original menu close/delete, mobile agenda")
        finally:
            if browser: browser.terminate(); browser.wait(timeout=15)
            server.terminate(); server.wait(timeout=15)


if __name__ == "__main__": run()
