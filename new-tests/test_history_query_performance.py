"""Run the production history query against isolated in-memory SQLite storage."""
import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest
from sqlalchemy import Column, String, Float, DateTime, create_engine, event, func
from sqlalchemy.orm import declarative_base, Session

Base = declarative_base()
class Course(Base):
    __tablename__ = 'courses'
    id = Column(String, primary_key=True)
    code = Column(String)
class Meeting(Base):
    __tablename__ = 'sessions'
    id = Column(String, primary_key=True)
    course_id = Column(String)
    name = Column(String)
class CheckIn(Base):
    __tablename__ = 'checkins'
    id = Column(String, primary_key=True)
    student_id = Column(String)
    session_id = Column(String)
    status = Column(String)
    appealed_at = Column(DateTime)
    reviewed_at = Column(DateTime)
    checked_in_at = Column(DateTime)
    risk_score = Column(Float)

class HistoryQueryTest(unittest.TestCase):
    def test_filtered_pages_use_one_select_and_keep_owner_scope(self):
        source = Path('/app/app/main.py')
        if not source.exists():
            source = Path('module2-backend/app/main.py')
        tree = ast.parse(source.read_text())
        handler = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'list_my_checkins')
        handler.decorator_list = []
        ns = dict(CheckIn=CheckIn, SessionModel=Meeting, Course=Course, User=object,
                  Session=Session, func=func, Depends=lambda value: None,
                  require_roles=lambda *args, **kwargs: None, get_read_db=None)
        exec(compile(ast.Module(body=[handler], type_ignores=[]), str(source), 'exec'), ns)
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        statements = []
        with Session(engine) as db:
            db.add_all([Course(id='c', code='CS'), Meeting(id='s', course_id='c', name='Lecture %_ networks')])
            for i in range(125):
                db.add(CheckIn(id=f'{i:03}', student_id='owner' if i < 120 else 'other', session_id='s', status='rejected', checked_in_at=datetime(2026, 10, 23), risk_score=0.15))
            db.commit()
            event.listen(engine, 'before_cursor_execute', lambda *args: statements.append(args[2]))
            for offset, count in [(0, 50), (50, 50), (100, 20), (150, 0)]:
                statements.clear()
                result = ns['list_my_checkins'](course_id='c', session_id='s', session_name=' LECTURE %_ ', offset=offset,
                    current_user=SimpleNamespace(id='owner'), db=db)
                self.assertEqual(len(result), count)
                self.assertEqual(len(statements), 1)
                if result:
                    self.assertEqual(result[0]['id'], f'{offset:03}')
                    self.assertEqual(result[0]['session_name'], 'Lecture %_ networks')
                    self.assertEqual(result[0]['risk_score'], 0.15)
            self.assertEqual(ns['list_my_checkins'](session_name='not found', current_user=SimpleNamespace(id='owner'), db=db), [])
        engine.dispose()

if __name__ == '__main__': unittest.main()
