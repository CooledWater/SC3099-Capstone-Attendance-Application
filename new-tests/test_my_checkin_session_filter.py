"""Verify the student-owned session filter runs before the history limit."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

class Field:
    def __init__(self, name): self.name = name
    def __eq__(self, value): return (self.name, value)
    def desc(self): return self

class Query:
    def __init__(self): self.calls = []
    def filter(self, expression): self.calls.append(('filter', expression)); return self
    def order_by(self, *args): return self
    def limit(self, value): self.calls.append(('limit', value)); return self
    def all(self): return []

class SessionFilterTest(unittest.TestCase):
    def test_student_and_session_filters_precede_limit(self):
        path = Path(__file__).resolve().parents[1] / 'module2-backend/app/main.py'
        tree = ast.parse(path.read_text())
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'list_my_checkins')
        fn.decorator_list = []
        model = SimpleNamespace(student_id=Field('student_id'), session_id=Field('session_id'), checked_in_at=Field('checked_in_at'))
        ns = dict(CheckIn=model, User=object, Session=object, Depends=lambda value: None, require_roles=lambda *roles: None, get_db=None)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), ns)
        query = Query()
        result = ns['list_my_checkins'](session_id='selected-session', limit=1, current_user=SimpleNamespace(id='current-student'), db=SimpleNamespace(query=lambda model: query))
        self.assertEqual(result, [])
        self.assertEqual(query.calls, [('filter', ('student_id', 'current-student')), ('filter', ('session_id', 'selected-session')), ('limit', 1)])

if __name__ == '__main__': unittest.main()
