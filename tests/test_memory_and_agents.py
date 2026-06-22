import uuid
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import Base
from app.models.memory import Memory
from app.models.message import Message
from app.models.user import User
from app.schemas.message import RouteMode
from app.services.agents import AgentCoordinator, ChatAgent, RouterAgent
from app.services.embedding_service import EmbeddingService
from app.services.memory_service import MemoryService
from app.services.stream_events import StreamEvent


class FakeHttpClient:
    def __init__(self, payload):
        self.payload = payload
        self.last_request = None

    def request_json(self, url, *, method, headers, body, timeout):
        self.last_request = {
            "url": url,
            "method": method,
            "headers": headers,
            "body": body,
            "timeout": timeout,
        }
        return self.payload


class FakeEmbeddingService:
    def __init__(self, vectors):
        self.vectors = vectors

    def embed(self, text):
        return self.vectors[text]


class FakeAIClient:
    def __init__(self, content):
        self.content = content

    def complete_chat(self, messages, tools=None, max_tokens=None):
        return {"content": self.content}


class EmbeddingServiceTests(unittest.TestCase):
    def test_embed_parses_openai_compatible_response(self):
        old_dimensions = settings.memory_embedding_dimensions
        old_key = settings.memory_embedding_api_key
        old_base_url = settings.memory_embedding_base_url
        try:
            settings.memory_embedding_dimensions = 3
            settings.memory_embedding_api_key = "test-key"
            settings.memory_embedding_base_url = "https://embeddings.example/v1"
            http = FakeHttpClient({"data": [{"embedding": [0.1, 0.2, 0.3]}]})

            result = EmbeddingService(http).embed("hello")

            self.assertEqual(result, [0.1, 0.2, 0.3])
            self.assertEqual(http.last_request["url"], "https://embeddings.example/v1/embeddings")
            self.assertEqual(http.last_request["body"]["input"], "hello")
        finally:
            settings.memory_embedding_dimensions = old_dimensions
            settings.memory_embedding_api_key = old_key
            settings.memory_embedding_base_url = old_base_url

    def test_embed_rejects_dimension_mismatch(self):
        old_dimensions = settings.memory_embedding_dimensions
        old_key = settings.memory_embedding_api_key
        old_base_url = settings.memory_embedding_base_url
        try:
            settings.memory_embedding_dimensions = 4
            settings.memory_embedding_api_key = "test-key"
            settings.memory_embedding_base_url = "https://embeddings.example/v1"
            service = EmbeddingService(FakeHttpClient({"data": [{"embedding": [0.1, 0.2]}]}))

            with self.assertRaises(Exception):
                service.embed("hello")
        finally:
            settings.memory_embedding_dimensions = old_dimensions
            settings.memory_embedding_api_key = old_key
            settings.memory_embedding_base_url = old_base_url


class MemoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=self.user_id, email="user@example.com", hashed_password="x", display_name="User"))
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def test_store_and_search_memories_are_scoped_to_user(self):
        other_user_id = uuid.uuid4()
        matcha_vector = self._vector(0)
        running_vector = self._vector(1)
        with self.Session() as db:
            db.add(User(id=other_user_id, email="other@example.com", hashed_password="x", display_name="Other"))
            db.add(Memory(user_id=self.user_id, content="用户喜欢抹茶", embedding=matcha_vector, importance=0.8))
            db.add(Memory(user_id=self.user_id, content="用户喜欢夜跑", embedding=running_vector, importance=0.7))
            db.add(Memory(user_id=other_user_id, content="其他用户喜欢抹茶", embedding=matcha_vector, importance=1.0))
            db.commit()

        service = MemoryService(
            FakeEmbeddingService({"抹茶": matcha_vector}),
            FakeAIClient("[]"),
            self.Session,
            enabled=True,
            max_results=1,
        )

        results = service.search_memories(self.user_id, "抹茶")

        self.assertEqual([memory.content for memory in results], ["用户喜欢抹茶"])

    def _vector(self, hot_index):
        vector = [0.0] * settings.memory_embedding_dimensions
        vector[hot_index] = 1.0
        return vector

    def test_extract_memories_parses_json_and_skips_invalid_items(self):
        service = MemoryService(
            FakeEmbeddingService({}),
            FakeAIClient('[{"content":"用户叫小林","importance":0.9},{"content":""},{"content":"用户喜欢咖啡","importance":"bad"}]'),
            self.Session,
            enabled=True,
        )

        candidates = service.extract_memories("用户说他叫小林，也喜欢咖啡")

        self.assertEqual([item.content for item in candidates], ["用户叫小林", "用户喜欢咖啡"])
        self.assertEqual(candidates[0].importance, 0.9)
        self.assertEqual(candidates[1].importance, 0.5)


class RouterAgentTests(unittest.TestCase):
    def test_router_reaches_expected_accuracy_on_examples(self):
        router = RouterAgent()
        examples = [
            ("今天有点累，陪我聊聊", RouteMode.CHAT),
            ("我刚刚考完试，心情很复杂", RouteMode.CHAT),
            ("你觉得我应该怎么调整心态", RouteMode.CHAT),
            ("帮我查询今天香港天气", RouteMode.AGENT),
            ("总结这个网页 https://example.com", RouteMode.AGENT),
            ("请运行工具抓取网页内容", RouteMode.AGENT),
            ("列出接下来三件待办", RouteMode.AGENT),
            ("翻译这段英文", RouteMode.AGENT),
            ("我想吃甜品", RouteMode.CHAT),
            ("搜索一下 pgvector 是什么", RouteMode.AGENT),
        ]

        correct = sum(1 for text, expected in examples if router.route(text).target is expected)

        self.assertGreaterEqual(correct / len(examples), 0.8)


class AgentCoordinatorTests(unittest.TestCase):
    def test_auto_routes_to_task_and_injects_memory(self):
        memory_agent = FakeMemoryAgent(["用户喜欢抹茶"])
        task_agent = FakeTaskAgent()
        coordinator = AgentCoordinator(RouterAgent(), ChatAgent(), task_agent, memory_agent)

        plan = coordinator.prepare(
            requested_route_mode=RouteMode.AUTO,
            user_id=uuid.uuid4(),
            content="帮我查询今天香港天气",
            history=[],
        )

        self.assertEqual(plan.route_mode, RouteMode.AGENT)
        self.assertEqual(plan.memory_context, ["用户喜欢抹茶"])
        self.assertIn("用户喜欢抹茶", str(plan.messages))
        self.assertEqual(plan.progress_events[0].event, "progress")

    def test_manual_chat_override_skips_task_agent(self):
        memory_agent = FakeMemoryAgent([])
        task_agent = FakeTaskAgent()
        coordinator = AgentCoordinator(RouterAgent(), ChatAgent(), task_agent, memory_agent)

        plan = coordinator.prepare(
            requested_route_mode=RouteMode.CHAT,
            user_id=uuid.uuid4(),
            content="帮我查询天气",
            history=[],
        )

        self.assertEqual(plan.route_mode, RouteMode.CHAT)
        self.assertFalse(task_agent.was_called)

    def test_auto_keeps_agent_mode_for_short_follow_up_answer(self):
        memory_agent = FakeMemoryAgent([])
        task_agent = FakeTaskAgent()
        coordinator = AgentCoordinator(RouterAgent(), ChatAgent(), task_agent, memory_agent)

        history = [
            Message(role="user", content="今天天气怎么样", route_mode=RouteMode.AGENT.value),
            Message(role="assistant", content="你所在的城市是哪里呀？", route_mode=RouteMode.AGENT.value),
        ]

        plan = coordinator.prepare(
            requested_route_mode=RouteMode.AUTO,
            user_id=uuid.uuid4(),
            content="我在广州",
            history=history,
        )

        self.assertEqual(plan.route_mode, RouteMode.AGENT)
        self.assertTrue(task_agent.was_called)


class FakeMemoryAgent:
    def __init__(self, memories):
        self.memories = memories

    def search(self, user_id, query):
        return self.memories

    @staticmethod
    def is_recall_question(content: str) -> bool:
        return False

    def search_for_recall(self, user_id, content, top_k=5):
        return self.memories[:top_k]

    def build_recall_context(self, memories):
        if not memories:
            return "未找到相关长期记忆。"
        return "\n".join(memories)


class FakeTaskAgent:
    def __init__(self):
        self.was_called = False

    def build_messages(self, content, history, memory_context=None):
        self.was_called = True
        return (
            [{"role": "system", "content": "\n".join(memory_context or [])}, {"role": "user", "content": content}],
            [StreamEvent("progress", {"skill_name": "router", "message": "task", "percent": 0.1})],
        )

    def run(self, messages, history):
        yield "done"


if __name__ == "__main__":
    unittest.main()
