"""Exercise the production appeal handler without touching shared databases."""
import ast
from datetime import datetime, timedelta
import html
from pathlib import Path
from types import SimpleNamespace
import unittest

class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail

class AppealContractTest(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'module2-backend/app/main.py'
        tree = ast.parse(path.read_text())
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'appeal_checkin')
        fn.decorator_list = []
        self.now = datetime(2026, 10, 23, 12)
        self.record = SimpleNamespace(id='record', student_id='student', status='rejected', appealed_at=None, checked_in_at=self.now - timedelta(days=1), session_id='session')
        self.audit = []
        self.commits = []
        self.locks = []
        def load(db, checkin_id, lock=False):
            self.locks.append(lock)
            if checkin_id == 'missing': raise HTTPException(404, 'Check-in not found')
            return self.record, None, None
        self.ns = dict(CheckInAppeal=object, User=object, Session=object, Depends=lambda x: None,
                       require_roles=lambda *roles: None, get_db=None, HTTPException=HTTPException,
                       status=SimpleNamespace(HTTP_400_BAD_REQUEST=400, HTTP_403_FORBIDDEN=403),
                       _load_checkin=load, datetime=SimpleNamespace(utcnow=lambda: self.now), html=html,
                       APPEALABLE_STATUSES=('flagged', 'rejected'), APPEAL_WINDOW=timedelta(days=7),
                       create_audit_log=lambda *args, **kwargs: self.audit.append((args, kwargs)))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), self.ns)

    def appeal(self, reason='I attended', owner='student', record_id='record'):
        return self.ns['appeal_checkin'](record_id, SimpleNamespace(appeal_reason=reason),
                    SimpleNamespace(id=owner), SimpleNamespace(commit=lambda: self.commits.append(True)))

    def test_both_eligible_statuses_save_reason_timestamp_and_audit(self):
        for status in ('flagged', 'rejected'):
            with self.subTest(status=status):
                self.setUp()
                self.record.status = status
                result = self.appeal('  <b>I attended</b>  ')
                self.assertEqual(result['status'], 'appealed')
                self.assertEqual(result['appealed_at'], self.now)
                self.assertEqual(result['appeal_reason'], '&lt;b&gt;I attended&lt;/b&gt;')
                self.assertEqual(self.audit[0][0][1], 'checkin_appealed')
                self.assertEqual(self.commits, [True])
                self.assertEqual(self.locks, [True])

    def test_invalid_status_ownership_repeat_expiry_and_blank_reason(self):
        cases = [('approved', None, 1, 'student', 'reason', 400),
                 ('pending', None, 1, 'student', 'reason', 400),
                 ('appealed', self.now, 1, 'student', 'reason', 400),
                 ('rejected', self.now, 1, 'student', 'reason', 400),
                 ('flagged', None, 1, 'other', 'reason', 403),
                 ('rejected', None, 8, 'student', 'reason', 400),
                 ('rejected', None, 1, 'student', '   ', 400)]
        for status, appealed_at, days, owner, reason, expected in cases:
            with self.subTest(status=status, owner=owner, days=days, reason=reason):
                self.setUp()
                self.record.status, self.record.appealed_at = status, appealed_at
                self.record.checked_in_at = self.now - timedelta(days=days)
                with self.assertRaises(HTTPException) as error: self.appeal(reason, owner)
                self.assertEqual(error.exception.status_code, expected)
                self.assertEqual(self.commits, [])

    def test_seven_day_boundary_is_inclusive(self):
        self.record.checked_in_at = self.now - timedelta(days=7)
        self.assertEqual(self.appeal()['status'], 'appealed')

    def test_missing_record(self):
        with self.assertRaises(HTTPException) as error: self.appeal(record_id='missing')
        self.assertEqual(error.exception.status_code, 404)

if __name__ == '__main__': unittest.main()
