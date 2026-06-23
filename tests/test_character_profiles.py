import uuid
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ConflictError, NotFoundError
from app.db.session import Base
from app.models.conversation import Conversation
from app.models.character_profile import ConversationCharacter
from app.models.user import User
from app.schemas.character_profile import (
    CharacterProfileCreate,
    CharacterProfileUpdate,
    ConversationCharactersRequest,
)
from app.services.character_profile_service import CharacterProfileService


class CharacterProfileServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)
        self.user_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=self.user_id, email="cp@t.com", hashed_password="x", display_name="CP"))
            db.commit()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _svc(self) -> CharacterProfileService:
        return CharacterProfileService(self.Session())

    def _create(self, name="TestChar", persona="A persona", color="#ff0000"):
        return self._svc().create(
            self.user_id,
            CharacterProfileCreate(name=name, persona=persona, color=color),
        )

    # ── CRUD ──

    def test_create_and_list(self):
        created = self._create()
        self.assertEqual(created.name, "TestChar")
        profiles = self._svc().list_by_user(self.user_id)
        self.assertEqual(len(profiles), 1)

    def test_create_duplicate_name_raises_conflict(self):
        self._create(name="Unique")
        with self.assertRaises(ConflictError):
            self._create(name="Unique")

    def test_get_by_id(self):
        created = self._create()
        fetched = self._svc().get(created.id, self.user_id)
        self.assertEqual(fetched.name, created.name)

    def test_get_nonexistent_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            self._svc().get(uuid.uuid4(), self.user_id)

    def test_update(self):
        created = self._create()
        updated = self._svc().update(
            created.id, self.user_id,
            CharacterProfileUpdate(persona="Updated persona"),
        )
        self.assertEqual(updated.persona, "Updated persona")

    def test_delete(self):
        created = self._create()
        self._svc().delete(created.id, self.user_id)
        with self.assertRaises(NotFoundError):
            self._svc().get(created.id, self.user_id)

    # ── Cross-user isolation ──

    def test_list_is_user_scoped(self):
        other_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=other_id, email="o@t.com", hashed_password="x", display_name="O"))
            db.commit()
        self._create(name="Mine")
        other_svc = CharacterProfileService(self.Session())
        self.assertEqual(other_svc.list_by_user(other_id), [])

    def test_get_fails_cross_user(self):
        other_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=other_id, email="o2@t.com", hashed_password="x", display_name="O2"))
            db.commit()
        created = self._create(name="Mine")
        out = self._svc().get(created.id, self.user_id)
        self.assertEqual(out.name, "Mine")
        # Other user should NOT be able to access
        other_svc = CharacterProfileService(self.Session())
        with self.assertRaises(NotFoundError):
            other_svc.get(created.id, other_id)

    def test_cross_user_duplicate_name_allowed(self):
        """Same name across different users should not cause conflict."""
        other_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=other_id, email="o3@t.com", hashed_password="x", display_name="O3"))
            db.commit()
        self._create(name="SharedName")
        other_svc = CharacterProfileService(self.Session())
        created = other_svc.create(
            other_id,
            CharacterProfileCreate(name="SharedName", persona="Other persona"),
        )
        self.assertEqual(created.name, "SharedName")

    # ── Conversation characters ──

    def _create_conv(self) -> uuid.UUID:
        with self.Session() as db:
            conv = Conversation(user_id=self.user_id, title="Conv")
            db.add(conv)
            db.commit()
            return conv.id

    def test_set_conversation_characters_requires_ownership(self):
        char = self._create()
        other_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=other_id, email="o4@t.com", hashed_password="x", display_name="O4"))
            db.commit()
        conv_id = self._create_conv()

        # Other user trying to set characters on user A's conversation
        other_svc = CharacterProfileService(self.Session())
        with self.assertRaises(NotFoundError):
            other_svc.set_conversation_characters(
                other_id,
                ConversationCharactersRequest(
                    character_ids=[char.id], conversation_id=conv_id,
                ),
            )

    def test_set_and_get_conversation_characters(self):
        conv_id = self._create_conv()
        char1 = self._create(name="Char1")
        char2 = self._create(name="Char2")

        result = self._svc().set_conversation_characters(
            self.user_id,
            ConversationCharactersRequest(
                character_ids=[char1.id, char2.id], conversation_id=conv_id,
            ),
        )
        self.assertEqual(len(result.character_ids), 2)

        chars = self._svc().get_conversation_characters(conv_id, self.user_id)
        self.assertEqual(len(chars), 2)
        self.assertEqual({c.name for c in chars}, {"Char1", "Char2"})

    def test_set_conversation_characters_validates_profile_ownership(self):
        """A character from another user cannot be added to a conversation."""
        other_id = uuid.uuid4()
        with self.Session() as db:
            db.add(User(id=other_id, email="o5@t.com", hashed_password="x", display_name="O5"))
            db.commit()
        other_svc = CharacterProfileService(self.Session())
        other_char = other_svc.create(
            other_id,
            CharacterProfileCreate(name="OtherChar", persona="P"),
        )
        conv_id = self._create_conv()

        with self.assertRaises(NotFoundError):
            self._svc().set_conversation_characters(
                self.user_id,
                ConversationCharactersRequest(
                    character_ids=[other_char.id], conversation_id=conv_id,
                ),
            )

    def test_conversation_character_unique_constraint(self):
        conv_id = self._create_conv()
        char = self._create()
        # Set once
        self._svc().set_conversation_characters(
            self.user_id,
            ConversationCharactersRequest(
                character_ids=[char.id], conversation_id=conv_id,
            ),
        )
        # Re-setting should replace, not cause duplicate
        result = self._svc().set_conversation_characters(
            self.user_id,
            ConversationCharactersRequest(
                character_ids=[char.id], conversation_id=conv_id,
            ),
        )
        self.assertEqual(len(result.character_ids), 1)
