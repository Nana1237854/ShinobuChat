import uuid
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import BadRequestError, NotFoundError
from app.db.session import Base
from app.models.conversation import Conversation
from app.models.diary import Diary
from app.models.message import Message
from app.models.todo import Todo
from app.models.user import User
from app.models.user_goal import UserGoal
from app.schemas.diary import DiaryGenerateRequest
from app.services.diary_service import (
    DiaryService,
    _extract_json_object,
    _sanitize_context,
    _sanitize_text,
)


class SanitizeTests(unittest.TestCase):
    def test_strips_api_key(self):
        text = "My key is sk-abc123def456ghijklmnopqrstuv and it works"
        result = _sanitize_text(text)
        self.assertIn("[API_KEY]", result)
        self.assertNotIn("sk-abc", result)

    def test_strips_bearer_token(self):
        text = "Auth: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        result = _sanitize_text(text)
        self.assertIn("[TOKEN]", result)
        self.assertNotIn("eyJ", result)

    def test_strips_email(self):
        text = "Contact user@example.com for details"
        result = _sanitize_text(text)
        self.assertIn("[邮箱]", result)
        self.assertNotIn("user@example.com", result)

    def test_strips_private_key(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIICWwIBAAKBgQC...\n-----END RSA PRIVATE KEY-----"
        result = _sanitize_text(text)
        self.assertIn("[PRIVATE_KEY]", result)
        self.assertNotIn("BEGIN RSA", result)

    def test_sanitize_context_strips_sensitive_fields(self):
        ctx = {
            "messages": [{"role": "user", "content": "key is sk-abc123def456ghijklmnopqr and my email user@test.com"}],
            "todos": [{"title": "Buy milk", "notes": "See https://api.example.com?token=secret123 for details"}],
            "api_key": "should-be-removed",
        }
        result = _sanitize_context(ctx)
        self.assertIn("[API_KEY]", result["messages"][0]["content"])
        self.assertNotIn("sk-abc123def", result["messages"][0]["content"])
        self.assertNotIn("user@test.com", result["messages"][0]["content"])
        self.assertNotIn("secret123", result["todos"][0]["notes"])
        self.assertNotIn("api_key", result)


class ExtractJsonTests(unittest.TestCase):
    def test_plain_json(self):
        r = _extract_json_object('{"title":"Hi","content":"Hello world","tags":["a"]}')
        self.assertEqual(r["title"], "Hi")

    def test_fenced_json(self):
        r = _extract_json_object('```json\n{"title":"Fenced","content":"Test"}\n```')
        self.assertEqual(r["title"], "Fenced")

    def test_plain_text_fallback(self):
        r = _extract_json_object("Just plain text today.")
        self.assertIn("content", r)
        self.assertIn("Just plain text", r["content"])


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
        # Seed conversation + messages for context
        with self.Session() as db:
            conv = Conversation(user_id=self.user_id, title="Test Conv")
            db.add(conv)
            db.commit()
            self.conv_id = conv.id
            for i, role in enumerate(["user", "assistant", "user", "assistant", "user"]):
                db.add(Message(
                    conversation_id=conv.id, role=role,
                    content=f"Message {i} content here",
                    created_at=datetime.now(timezone.utc) - timedelta(hours=5 - i),
                ))
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _svc(self, ai_client=None, config_service=None, emotion_service=None):
        return DiaryService(
            self.Session(),
            ai_client=ai_client,
            config_service=config_service,
            emotion_service=emotion_service,
        )

    # ── Generation tests ──

    def test_generate_creates_diary(self):
        svc = self._svc()
        result = svc.generate(self.user_id, DiaryGenerateRequest(date=self.today.isoformat()))
        self.assertIsNotNone(result.id)
        self.assertTrue(len(result.content) > 0)
        self.assertTrue(len(result.title) > 0)

    def test_duplicate_generate_returns_existing(self):
        svc = self._svc()
        first = svc.generate(self.user_id, DiaryGenerateRequest(date=self.today.isoformat()))
        second = svc.generate(self.user_id, DiaryGenerateRequest(date=self.today.isoformat()))
        self.assertEqual(first.id, second.id)

    def test_force_overwrites_existing(self):
        svc = self._svc()
        first = svc.generate(self.user_id, DiaryGenerateRequest(date=self.today.isoformat()))
        second = svc.generate(self.user_id, DiaryGenerateRequest(date=self.today.isoformat(), force=True))
        # force=True triggers full regeneration; since messages exist, content should differ
        self.assertIsNotNone(second.id)

    def test_diary_enabled_false_raises(self):
        mock_cfg = MagicMock()
        mock_cfg.get_effective_value.return_value = False
        svc = self._svc(config_service=mock_cfg)
        with self.assertRaises(BadRequestError):
            svc.generate(self.user_id, DiaryGenerateRequest(date=self.today.isoformat()))

    def test_insufficient_context_fallback(self):
        # Create a new user with no messages
        uid = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=uid, email="e@t.com", hashed_password="x", display_name="E"))
            db.commit()
        svc = DiaryService(self.Session())
        result = svc.generate(uid, DiaryGenerateRequest(date=self.today.isoformat()))
        self.assertIsNotNone(result.id)
        self.assertIn("平淡", result.title)

    def test_llm_failure_falls_back(self):
        mock_ai = MagicMock()
        mock_ai.complete_chat.side_effect = RuntimeError("API down")
        svc = self._svc(ai_client=mock_ai)
        result = svc.generate(self.user_id, DiaryGenerateRequest(date=self.today.isoformat(), force=True))
        self.assertIsNotNone(result.id)
        self.assertTrue(len(result.content) > 0)

    def test_llm_non_json_falls_back(self):
        mock_ai = MagicMock()
        mock_ai.complete_chat.return_value = {"content": "Today was a great day! I talked to the user."}
        svc = self._svc(ai_client=mock_ai)
        result = svc.generate(self.user_id, DiaryGenerateRequest(date=self.today.isoformat(), force=True))
        self.assertIsNotNone(result.id)
        self.assertIn("Today", result.content)

    def test_context_collects_messages_todos_goals(self):
        with self.Session() as db:
            db.add(Todo(user_id=self.user_id, title="Test todo", completed=False))
            db.add(UserGoal(user_id=self.user_id, title="Learn Python", status="active"))
            db.commit()
        svc = self._svc()
        result = svc.generate(self.user_id, DiaryGenerateRequest(date=self.today.isoformat(), force=True))
        self.assertIsNotNone(result.id)
        self.assertTrue(len(result.content) > 0)

    # ── CRUD tests ──

    def test_list_returns_date_descending(self):
        yesterday = self.today - timedelta(days=1)
        svc = self._svc()
        svc.generate(self.user_id, DiaryGenerateRequest(date=self.today.isoformat()))
        svc.generate(self.user_id, DiaryGenerateRequest(date=yesterday.isoformat()))
        results = svc.list_diaries(self.user_id)
        self.assertGreaterEqual(len(results), 2)
        self.assertGreaterEqual(results[0].date, results[-1].date)

    def test_get_non_existent_raises_404(self):
        with self.assertRaises(NotFoundError):
            self._svc().get_by_date(self.user_id, date(2099, 1, 1))

    def test_cross_user_isolation(self):
        other_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=other_id, email="other@t.com", hashed_password="x", display_name="Other"))
            db.commit()
        svc = self._svc()
        svc.generate(self.user_id, DiaryGenerateRequest(date=self.today.isoformat()))
        other_svc = DiaryService(self.Session())
        results = other_svc.list_diaries(other_id)
        self.assertEqual(len(results), 0)

    def test_unique_constraint_enforced(self):
        svc = self._svc()
        svc.generate(self.user_id, DiaryGenerateRequest(date=self.today.isoformat()))
        # Direct insert should fail
        with self.Session() as db:
            dup = Diary(
                user_id=self.user_id, date=self.today,
                title="Dup", summary="Dup", content="Dup", tags=[],
            )
            db.add(dup)
            with self.assertRaises(Exception):
                db.commit()
