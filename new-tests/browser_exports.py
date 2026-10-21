"""Exercise the built Export tab with mocked APIs and intercepted downloads."""
import base64
import json
import os
import subprocess
import tempfile
import time
from urllib.parse import urlparse, parse_qs
import httpx
from websockets.sync.client import connect
from browser_enrollments import Browser, EDGE, ROOT, port


class ExportBrowser(Browser):
    export_error = False
    empty = False

    def route(self, event):
        request = event['request']
        url = urlparse(request['url'])
        if '/export/attendance/' not in url.path:
            return super().route(event)
        query = parse_qs(url.query)
        self.requests.append((request['method'], url.path, query, None))
        code = 403 if self.export_error else 200
        columns = ['student_id', 'student_name', 'student_email', 'session_date', 'session_name', 'status', 'checked_in_at', 'risk_score']
        data = [] if self.empty else [dict(zip(columns, ['123', 'Student One', 'one@example.edu', '2026-10-21', 'Lecture', 'approved', '2026-10-21T08:00:00Z', 0.1]))]
        body = json.dumps({'detail': 'No export permission'} if self.export_error else data)
        content_type = 'application/json'
        if query.get('format') == ['csv'] and not self.export_error:
            content_type = 'text/csv'
            body = ','.join(columns) + '\r\n123,Student One,one@example.edu,2026-10-21,Lecture,approved,2026-10-21T08:00:00Z,0.1\r\n'
        headers = [{'name': 'Content-Type', 'value': content_type}, {'name': 'Content-Disposition', 'value': 'attachment; filename="server-attendance.csv"'}, {'name': 'Access-Control-Allow-Origin', 'value': request['headers'].get('Origin', '*')}, {'name': 'Access-Control-Allow-Credentials', 'value': 'true'}, {'name': 'Access-Control-Allow-Headers', 'value': 'authorization,content-type,accept'}, {'name': 'Access-Control-Expose-Headers', 'value': 'Content-Disposition'}]
        self.sequence += 1
        self.ws.send(json.dumps({'id': self.sequence, 'method': 'Fetch.fulfillRequest', 'params': {'requestId': event['requestId'], 'responseCode': 204 if request['method'] == 'OPTIONS' else code, 'responseHeaders': headers, 'body': base64.b64encode(body.encode()).decode()}}))


with tempfile.TemporaryDirectory(prefix='export-browser-', ignore_cleanup_errors=True) as temporary:
    web, debug = port(), port()
    hidden = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    with tempfile.TemporaryFile() as log:
        server = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', str(web)], cwd=ROOT / 'module4-observability', stdout=log, stderr=log, creationflags=hidden)
        browser = None
        try:
            for _ in range(100):
                try:
                    if httpx.get(f'http://127.0.0.1:{web}').status_code == 200: break
                except httpx.TransportError: pass
                time.sleep(.1)
            browser = subprocess.Popen([EDGE, '--headless=new', '--no-first-run', f'--user-data-dir={temporary}', f'--remote-debugging-port={debug}', 'about:blank'], stdout=log, stderr=log, creationflags=hidden)
            for _ in range(100):
                try:
                    page = next(p for p in httpx.get(f'http://127.0.0.1:{debug}/json/list').json() if p['type'] == 'page')
                    break
                except (httpx.TransportError, StopIteration): time.sleep(.1)
            with connect(page['webSocketDebuggerUrl'], max_size=8_000_000) as ws:
                ui = ExportBrowser(ws)
                ui.command('Fetch.enable', {'patterns': [{'urlPattern': '*api/v1/*'}]})
                ui.command('Page.navigate', {'url': f'http://127.0.0.1:{web}'})
                ui.wait("document.body.innerText.includes('Enrollments')")
                ui.click('Export')
                ui.wait("document.body.innerText.includes('Export settings')")
                assert not ui.evaluate("document.body.innerText.toLowerCase().includes('preview')")
                ui.fill('input[aria-label="Start date"]', '2026-10-22')
                ui.fill('input[aria-label="End date"]', '2026-10-21')
                ui.wait("document.body.innerText.includes('Start date must not be after end date.')")
                ui.click('This month')
                # Capture the actual blob contents and filenames without writing personal files.
                ui.evaluate("window.downloads=[]; URL.createObjectURL=(b)=>{window.lastBlob=b; return 'blob:test'}; URL.revokeObjectURL=()=>{}; HTMLAnchorElement.prototype.click=function(){window.downloads.push({name:this.download,blob:window.lastBlob})}")
                ui.click('Download CSV')
                ui.wait('window.downloads.length === 1')
                assert ui.evaluate('window.downloads[0].name') == 'server-attendance.csv'
                ui.evaluate("window.downloads[0].blob.text().then(t=>window.csvText=t)")
                ui.wait("typeof window.csvText === 'string'")
                assert ui.evaluate("window.csvText").startswith('student_id,student_name')
                ui.evaluate("document.querySelector('input[value=json]').click()")
                ui.click('Download JSON')
                ui.wait('window.downloads.length === 2')
                ui.evaluate("window.downloads[1].blob.text().then(t=>window.jsonText=t)")
                ui.wait("typeof window.jsonText === 'string'")
                assert json.loads(ui.evaluate('window.jsonText'))[0]['student_name'] == 'Student One'
                ui.empty = True
                ui.click('Download JSON')
                ui.wait("document.body.innerText.includes('Downloaded an empty JSON array.')")
                ui.export_error = True
                ui.click('Download JSON')
                ui.wait("document.body.innerText.includes('No export permission')")
                assert ui.evaluate('window.downloads.length') == 3
                ui.command('Emulation.setDeviceMetricsOverride', dict(width=390, height=844, deviceScaleFactor=1, mobile=True))
                assert ui.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1')
                calls = [q for method, path, q, _ in ui.requests if '/export/attendance/' in path and method == 'GET']
                assert all(q['start_date'][0].endswith('T00:00:00+08:00') and q['end_date'][0].endswith('T23:59:59.999999+08:00') for q in calls)
                print('PASS: no preview, date validation, Singapore date bounds, server CSV filename/content, JSON array, empty/error states, mobile layout')
        finally:
            if browser: browser.terminate(); browser.wait(timeout=15)
            server.terminate(); server.wait(timeout=15)
