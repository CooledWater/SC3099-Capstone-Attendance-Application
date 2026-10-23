"""Verify the student-owned session filter runs before the history limit."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

class Field:
    def __init__(self, name): self.name = name
    def __eq__(self, value): return (self.name, value)
    def desc(self): return self
    def contains(self, value, autoescape=False): return ('contains', self.name, value, autoescape)

class Query:
    def __init__(self): self.calls = []
    def filter(self, expression): self.calls.append(('filter', expression)); return self
    def outerjoin(self, *args): return self
    def join(self, *args): self.calls.append(('join',)); return self
    def order_by(self, *args): return self
    def offset(self, value): self.calls.append(('offset', value)); return self
    def limit(self, value): self.calls.append(('limit', value)); return self
    def all(self): return []

class SessionFilterTest(unittest.TestCase):
    def test_history_retains_appeal_timestamp_after_rejection(self):
        from datetime import datetime
        path = Path(__file__).resolve().parents[1] / 'module2-backend/app/main.py'
        tree = ast.parse(path.read_text())
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'list_my_checkins')
        fn.decorator_list = []
        model = SimpleNamespace(id=Field('id'), student_id=Field('student_id'), session_id=Field('session_id'), checked_in_at=Field('checked_in_at'))
        ns = dict(CheckIn=model, SessionModel=SimpleNamespace(id=Field('id'), name=Field('name'), course_id=Field('course_id')), Course=SimpleNamespace(id=Field('id'), code=Field('code')), User=object, Session=object, Depends=lambda value: None, require_roles=lambda *roles, **kwargs: None, get_read_db=None)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), ns)
        for appealed_at in (None, datetime(2026, 10, 23, 1)):
            record = SimpleNamespace(id='checkin', session_id='session', status='rejected', appealed_at=appealed_at, reviewed_at=datetime(2026, 10, 23, 2), checked_in_at=datetime(2026, 10, 22), risk_score=0.6)
            query = Query()
            query.all = lambda: [(record, 'Lecture', 'CS', 'course')]
            query.first = lambda: None
            result = ns['list_my_checkins'](current_user=SimpleNamespace(id='student'), db=SimpleNamespace(query=lambda *models: query))
            self.assertEqual(result[0]['status'], 'rejected')
            self.assertEqual(result[0]['appealed_at'], appealed_at)
            self.assertEqual(result[0]['reviewed_at'], record.reviewed_at)

    def test_student_and_session_filters_precede_limit(self):
        path = Path(__file__).resolve().parents[1] / 'module2-backend/app/main.py'
        tree = ast.parse(path.read_text())
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'list_my_checkins')
        fn.decorator_list = []
        model = SimpleNamespace(id=Field('id'), student_id=Field('student_id'), session_id=Field('session_id'), checked_in_at=Field('checked_in_at'))
        ns = dict(CheckIn=model, User=object, Session=object, Depends=lambda value: None, require_roles=lambda *roles, **kwargs: None, get_read_db=None)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), ns)
        ns['SessionModel'] = SimpleNamespace(id=Field('id'), course_id=Field('course_id'), name=Field('name'))
        ns['Course'] = SimpleNamespace(id=Field('id'), code=Field('code'))
        ns['func'] = SimpleNamespace(lower=lambda field: field)
        query = Query()
        result = ns['list_my_checkins'](session_id='selected-session', limit=50, offset=50, course_id='selected-course', session_name=' Lecture %_ ', current_user=SimpleNamespace(id='current-student'), db=SimpleNamespace(query=lambda *models: query))
        self.assertEqual(result, [])
        self.assertEqual(query.calls, [('filter', ('student_id', 'current-student')), ('filter', ('session_id', 'selected-session')), ('filter', ('course_id', 'selected-course')), ('filter', ('contains', 'name', 'lecture %_', True)), ('offset', 50), ('limit', 50)])

if __name__ == '__main__': unittest.main()
