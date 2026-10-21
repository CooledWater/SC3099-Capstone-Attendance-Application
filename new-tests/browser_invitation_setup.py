"""Headless Edge checks for the deployed student setup page, with mocked APIs."""
import base64
import json
import os
import subprocess
import tempfile
import time
from urllib.parse import urlparse

import httpx
from websockets.sync.client import connect
from browser_enrollments import Browser, EDGE, port


class SetupBrowser(Browser):
    def __init__(self, ws):
        super().__init__(ws)
        self.used = False

    def route(self, event):
        request = event["request"]
        path = urlparse(request["url"]).path
        payload = json.loads(request.get("postData", "{}"))
        code, body = 200, {}
        self.requests.append((request["method"], path, {}, request.get("postData")))
        if request["method"] == "OPTIONS":
            code, body = 204, None
        elif path.endswith("/invitations/validate"):
            if payload.get("token") == "valid-invitation" and not self.used:
                body = {"email": "new-student@example.edu"}
            else:
                code, body = 400, {"detail": "This invitation is invalid or expired. Request a new invitation."}
        elif path.endswith("/invitations/complete"):
            assert payload == {"token": "valid-invitation", "password": "new-password-123"}
            assert not self.used
            self.used = True
            body = {"email": "new-student@example.edu", "message": "Password set successfully"}
        elif path.endswith("/invitations/request"):
            assert payload["email"] == "new-student@example.edu"
            body = {"message": "If this account has a pending invitation, a new email will be sent. Please check your inbox."}
        elif path.endswith("/auth/dashboard/login") or path.endswith("/auth/dashboard/refresh"):
            body = {"access_token": "test-access", "user": {"id": "new-student", "email": "new-student@example.edu", "role": "student"}}
        elif path.endswith("/users/me"):
            body = {"id": "new-student", "full_name": "New Student", "email": "new-student@example.edu", "role": "student"}
        elif path.endswith("/sessions/active") or path.endswith("/enrollments/my-enrollments") or path.endswith("/checkins/my-checkins"):
            body = []
        self.sequence += 1
        origin = request["headers"].get("Origin", request["headers"].get("origin", "http://localhost:8501"))
        self.ws.send(json.dumps({"id": self.sequence, "method": "Fetch.fulfillRequest", "params": {
            "requestId": event["requestId"], "responseCode": code,
            "responseHeaders": [{"name": "Content-Type", "value": "application/json"}, {"name": "Access-Control-Allow-Origin", "value": origin}, {"name": "Access-Control-Allow-Credentials", "value": "true"}, {"name": "Access-Control-Allow-Headers", "value": "authorization,content-type,accept"}, {"name": "Access-Control-Allow-Methods", "value": "GET,POST,OPTIONS"}],
            "body": base64.b64encode(json.dumps(body).encode() if body is not None else b"").decode(),
        }}))


origin = os.getenv("SETUP_TEST_URL", "http://localhost:8501")
assert httpx.get(origin + "/setup-account").status_code == 200
with tempfile.TemporaryDirectory(prefix="invitation-setup-browser-", ignore_cleanup_errors=True) as temporary:
    debug_port = port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with tempfile.TemporaryFile() as log:
        browser = subprocess.Popen([EDGE, "--headless=new", "--no-first-run", "--no-default-browser-check", f"--user-data-dir={temporary}", f"--remote-debugging-port={debug_port}", "about:blank"], stdout=log, stderr=log, creationflags=hidden)
        try:
            for _ in range(100):
                try:
                    pages = httpx.get(f"http://127.0.0.1:{debug_port}/json/list").json()
                    page = next(page for page in pages if page["type"] == "page")
                    break
                except (httpx.TransportError, StopIteration):
                    time.sleep(0.1)
            with connect(page["webSocketDebuggerUrl"], max_size=8_000_000) as ws:
                ui = SetupBrowser(ws)
                ui.command("Fetch.enable", {"patterns": [{"urlPattern": "*api/v1/*"}]})
                ui.command("Page.navigate", {"url": origin + "/setup-account#token=valid-invitation"})
                ui.wait("document.body.innerText.includes('new-student@example.edu')")
                assert ui.evaluate("window.location.hash") == ""
                # Simulate a prior explicit logout; successful setup must clear it.
                ui.evaluate("sessionStorage.setItem('saiv.dashboard.signed-out', 'true')")
                ui.fill("input[autocomplete='new-password']", "new-password-123")
                # Inputs are in separate labels: select them explicitly for confirmation.
                ui.evaluate("(() => {const e=document.querySelectorAll('input[type=password]')[1]; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'different-password'); e.dispatchEvent(new Event('input',{bubbles:true}));})()")
                ui.click("Set password and sign in")
                ui.wait("document.body.innerText.includes('Passwords do not match.')")
                ui.evaluate("(() => {const e=document.querySelectorAll('input[type=password]')[0]; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'new-password-123'); e.dispatchEvent(new Event('input',{bubbles:true})); const c=document.querySelectorAll('input[type=password]')[1]; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(c,'new-password-123'); c.dispatchEvent(new Event('input',{bubbles:true}));})()")
                ui.evaluate("(() => {const b=Array.from(document.querySelectorAll('button')).find(e=>e.textContent==='Set password and sign in'); b.click(); b.click();})()")
                ui.wait("window.location.pathname === '/'")
                ui.wait("document.body.innerText.includes('Your check-in history')")
                assert ui.evaluate("sessionStorage.getItem('saiv.dashboard.signed-out')") is None
                assert len([request for request in ui.requests if request[0] == 'POST' and request[1].endswith('/invitations/complete')]) == 1
                ui.command("Page.navigate", {"url": origin + "/setup-account#token=expired-invitation"})
                ui.wait("document.body.innerText.includes('This invitation is invalid or expired.')")
                ui.fill("input[type=email]", "new-student@example.edu")
                ui.click("Request a new invitation")
                ui.wait("document.body.innerText.includes('Please check your inbox.')")
                ui.command("Emulation.setDeviceMetricsOverride", {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": True})
                assert ui.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
                print("PASS: fragment removal, password mismatch, one submission, sign-in redirect, expired invitation request, mobile layout")
                try:
                    ui.command("Browser.close")
                except Exception:
                    pass
        finally:
            browser.terminate()
            browser.wait(timeout=15)

