import uuid
import unittest
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import NotFoundError
from app.db.session import Base
from app.models.diary import Diary
from app.models.user import User
from app.services.diary_service import DiaryService


class DiaryServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        self.today = date.today()
        with self.Session() as db:
            db.add(User(id=self.user_id, email="d@t.com", hashed_password="x", display_name="D"))
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _svc(self) -> DiaryService:
        return DiaryService(self.Session())

    def _seed(self, **kwargs):
        with self.Session() as db:
            diary = Diary(
                user_id=self.user_id,
                date=kwargs.get("diary_date", self.today),
                title=kwargs.get("title", "Test"),
                summary=kwargs.get("summary", "Summary"),
                content=kwargs.get("content", "Content"),
                mood=kwargs.get("mood"),
                tags=kwargs.get("tags", []),
            )
            db.add(diary)
            db.commit()

    def test_list_returns_empty_when_no_diaries(self):
        self.assertEqual(self._svc().list_diaries(self.user_id), [])

    def test_list_returns_seeded_diary_as_diary_out(self):
        self._seed()
        results = self._svc().list_diaries(self.user_id)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Test")
        data = results[0].model_dump(by_alias=True)
        self.assertIn("diary_id", data)
        self.assertNotIn("id", data)

    def test_get_by_date_returns_detail(self):
        self._seed(diary_date=self.today)
        detail = self._svc().get_by_date(self.user_id, self.today)
        self.assertEqual(detail.content, "Content")
        self.assertIn("diary_id", detail.model_dump(by_alias=True))

    def test_get_by_date_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            self._svc().get_by_date(self.user_id, date(2099, 1, 1))

    def test_mood_filter(self):
        self._seed(mood="happy", title="Happy Day", diary_date=self.today)
        self._seed(mood="sad", title="Sad Day", diary_date=self.today - timedelta(days=1))
        results = self._svc().list_diaries(self.user_id, mood="happy")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Happy Day")

    def test_generate_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self._svc().generate(self.user_id)

    def test_cross_user_isolation(self):
        other_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=other_id, email="e@t.com", hashed_password="x", display_name="E"))
            db.commit()

        self._seed(title="Mine")
        # Other user sees nothing
        other_svc = DiaryService(self.Session())
        self.assertEqual(other_svc.list_diaries(other_id), [])
        # User A still sees theirs
        self.assertEqual(len(self._svc().list_diaries(self.user_id)), 1)

    def test_unique_constraint_user_date(self):
        self._seed(diary_date=self.today, title="First")
        with self.Session() as db:
            dup = Diary(
                user_id=self.user_id,
                date=self.today,
                title="Second",
                summary="S",
                content="C",
                tags=[],
            )
            db.add(dup)
            with self.assertRaises(Exception):
                db.commit()
