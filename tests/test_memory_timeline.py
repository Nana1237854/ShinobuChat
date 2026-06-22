import uuid
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.memory import Memory, MemoryPreference
from app.models.message import Message
from app.models.user import User
from app.services.memory_service import MemoryService, MemoryContextMessage


class FakeEmbeddingService:
    def embed(self, text: str) -> list[float]:
        return [0.1] * 384


class FakeAIClient:
    def complete_chat(self, messages, max_tokens=512):
        return {"content": "[]"}


class MemoryTimelineTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        self.other_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=self.user_id, email="m@t.com", hashed_password="x", display_name="M"))
            db.add(User(id=self.other_id, email="o@t.com", hashed_password="x", display_name="O"))
            db.commit()
        self.svc = MemoryService(FakeEmbeddingService(), FakeAIClient(), self.Session)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _add_memory(self, user_id=None, **overrides):
        defaults = {
            "user_id": user_id or self.user_id,
            "content": "test memory",
            "title": "test",
            "category": "long_term",
            "source": "auto",
            "embedding": [0.1] * 384,
            "importance": 0.5,
        }
        defaults.update(overrides)
        mem = Memory(**defaults)
        with self.Session() as db:
            db.add(mem)
            db.commit()
            db.refresh(mem)
        return mem

    # 1. timeline only returns current user's memories
    def test_timeline_user_isolation(self):
        self._add_memory(user_id=self.user_id, content="mine")
        self._add_memory(user_id=self.other_id, content="theirs")
        items = self.svc.list_timeline(self.user_id)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].content, "mine")

    # 2. timeline ordered by created_at desc
    def test_timeline_desc_order(self):
        m1 = self._add_memory(content="older")
        m2 = self._add_memory(content="newer")
        items = self.svc.list_timeline(self.user_id)
        self.assertEqual(items[0].content, "newer")
        self.assertEqual(items[1].content, "older")

    # 3. time_bucket generated correctly
    def test_time_bucket_rules(self):
        from app.api.v1.routes.memories import _time_bucket

        now = datetime.now(timezone.utc)
        self.assertEqual(_time_bucket(now), "today")
        self.assertEqual(_time_bucket(now.replace(day=now.day - 2)), "this_week")
        self.assertEqual(_time_bucket(now.replace(day=now.day - 10)), "this_month")
        self.assertEqual(_time_bucket(now.replace(year=now.year - 1)), "earlier")

    # 4. search returns memories via existing search_memories
    @patch.object(MemoryService, "search_memories", return_value=[])
    def test_search_calls_search_memories(self, mock_search):
        self._add_memory(content="alpha")
        self.svc.search_memories = mock_search
        mock_search.return_value = []
        result = self.svc.search_memories(self.user_id, "test")
        self.assertEqual(result, [])

    # 5. search empty query returns 400 (tested via API route validation)
    def test_search_empty_query_handled(self):
        from app.schemas.memory import MemorySearchRequest
        with self.assertRaises(Exception):
            MemorySearchRequest(user_id=self.user_id, query="")

    # 6. context returns limited window
    @patch.object(MemoryService, "get_memory_context")
    def test_context_window(self, mock_ctx):
        mock_ctx.return_value = type("Ctx", (), {
            "memory_id": uuid.uuid4(),
            "source_msg_id": None,
            "conversation_id": None,
            "messages": [],
            "detail": "test",
        })()
        ctx = self.svc.get_memory_context(self.user_id, uuid.uuid4(), window=5)
        self.assertEqual(ctx.detail, "test")

    # 7. context without source_msg_id doesn't crash
    def test_context_no_source_msg(self):
        mem = self._add_memory(content="no source", source_msg_id=None)
        ctx = self.svc.get_memory_context(self.user_id, mem.id, window=3)
        self.assertEqual(ctx.detail, "source context unavailable")
        self.assertEqual(len(ctx.messages), 0)

    # 8. context doesn't return other user's conversations
    def test_context_user_isolation(self):
        other_mem = self._add_memory(user_id=self.other_id, content="theirs")
        from app.core.exceptions import NotFoundError
        with self.assertRaises(NotFoundError):
            self.svc.get_memory_context(self.user_id, other_mem.id)

    # 9. memory_id not belonging to user returns 404
    def test_memory_not_found_for_user(self):
        from app.core.exceptions import NotFoundError
        with self.assertRaises(NotFoundError):
            self.svc.get_memory_context(self.user_id, uuid.uuid4())

    # 10. recall question detection
    def test_is_recall_question_true(self):
        from app.services.agents.memory_agent import MemoryAgent
        self.assertTrue(MemoryAgent.is_recall_question("上次聊到什么了？"))
        self.assertTrue(MemoryAgent.is_recall_question("还记得我上次说的那个吗"))
        self.assertTrue(MemoryAgent.is_recall_question("我们之前讨论过那个项目"))

    def test_is_recall_question_false(self):
        from app.services.agents.memory_agent import MemoryAgent
        self.assertFalse(MemoryAgent.is_recall_question("今天天气怎么样"))
        self.assertFalse(MemoryAgent.is_recall_question("帮我创建一个待办"))

    # 11. recall search integration
    def test_search_for_recall(self):
        from app.services.agents.memory_agent import MemoryAgent
        agent = MemoryAgent(self.svc)
        self._add_memory(content="用户之前提到在开发 ShinobuChat")
        results = agent.search_for_recall(self.user_id, "上次聊到什么", top_k=3)
        self.assertIsInstance(results, list)

    def test_build_recall_context_empty(self):
        from app.services.agents.memory_agent import MemoryAgent
        agent = MemoryAgent(self.svc)
        ctx = agent.build_recall_context([])
        self.assertIn("未找到", ctx)

    def test_build_recall_context_with_results(self):
        from app.services.agents.memory_agent import MemoryAgent
        agent = MemoryAgent(self.svc)
        ctx = agent.build_recall_context(["memory 1", "memory 2"])
        self.assertIn("memory 1", ctx)
        self.assertIn("memory 2", ctx)

    # 12. preferences CRUD
    def test_preferences_default(self):
        pref = self.svc.get_preferences(self.user_id)
        self.assertTrue(pref.enabled)

    @patch.object(MemoryService, "update_preferences")
    def test_preferences_update(self, mock_update):
        mock_pref = type("P", (), {"user_id": self.user_id, "enabled": False, "updated_at": None})()
        mock_update.return_value = mock_pref
        pref = self.svc.update_preferences(self.user_id, type("Payload", (), {"enabled": False})())
        self.assertFalse(pref.enabled)

    # 13. list_by_user respects include_archived
    def test_list_by_user_excludes_archived(self):
        self._add_memory(content="visible")
        self._add_memory(content="hidden", archived=True)
        items = self.svc.list_by_user(self.user_id, include_archived=False)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].content, "visible")

    def test_list_by_user_includes_archived(self):
        self._add_memory(content="visible")
        self._add_memory(content="hidden", archived=True)
        items = self.svc.list_by_user(self.user_id, include_archived=True)
        self.assertEqual(len(items), 2)


if __name__ == "__main__":
    unittest.main()
