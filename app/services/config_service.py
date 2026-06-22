from __future__ import annotations

import base64
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ConfigurationError
from app.core.time import local_now
from app.models.user_config import UserConfig
from app.schemas.user_config import UserConfigFieldOut, UserConfigOut, UserConfigPatch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConfigSpec:
    value_type: type
    encrypted: bool = False


CONFIG_SPECS: dict[str, ConfigSpec] = {
    "ai_api_key": ConfigSpec(str, True),
    "ai_base_url": ConfigSpec(str),
    "ai_model": ConfigSpec(str),
    "ai_request_timeout_seconds": ConfigSpec(int),
    "ai_supports_image_input": ConfigSpec(bool),
    "ai_lightweight_max_tokens": ConfigSpec(int),
    "roleplay_llm_model": ConfigSpec(str),
    "roleplay_llm_temperature": ConfigSpec(float),
    "decision_llm_model": ConfigSpec(str),
    "decision_llm_temperature": ConfigSpec(float),
    "google_search_api_key": ConfigSpec(str, True),
    "google_search_cx": ConfigSpec(str),
    "edge_tts_voice": ConfigSpec(str),
    "asr_engine": ConfigSpec(str),
    "whisper_api_key": ConfigSpec(str, True),
}


class ConfigService:
    def __init__(self, db: Session):
        self.db = db
        self._fernet = Fernet(self._fernet_key())

    def list_fields(self, user_id: UUID) -> UserConfigOut:
        rows = {
            row.field_name: row
            for row in self.db.query(UserConfig).filter(UserConfig.user_id == user_id).all()
        }
        fields: list[UserConfigFieldOut] = []
        for key, spec in CONFIG_SPECS.items():
            row = rows.get(key)
            if row is not None:
                value = self._decode_row(row)
                source = "user"
            else:
                value = getattr(settings, key)
                source = "env" if key in settings.model_fields_set else "default"
            fields.append(
                UserConfigFieldOut(
                    key=key,
                    value=self._mask(value) if spec.encrypted else value,
                    source=source,
                    encrypted=spec.encrypted,
                )
            )
        return UserConfigOut(fields=fields)

    def update(self, user_id: UUID, patch: UserConfigPatch) -> UserConfigOut:
        values = patch.model_dump(exclude_unset=True)
        for key, value in values.items():
            spec = CONFIG_SPECS[key]
            row = (
                self.db.query(UserConfig)
                .filter(UserConfig.user_id == user_id, UserConfig.field_name == key)
                .first()
            )
            if value is None:
                if row is not None:
                    self.db.delete(row)
                continue
            if spec.encrypted and self._looks_masked(value):
                continue
            serialized = self._serialize(value)
            if spec.encrypted:
                serialized = self._fernet.encrypt(serialized.encode("utf-8")).decode("ascii")
            if row is None:
                row = UserConfig(
                    user_id=user_id,
                    field_name=key,
                    field_value=serialized,
                    encrypted=spec.encrypted,
                )
            else:
                row.field_value = serialized
                row.encrypted = spec.encrypted
                row.updated_at = local_now()
            self.db.add(row)
        self.db.commit()
        return self.list_fields(user_id)

    def reset(self, user_id: UUID) -> UserConfigOut:
        self.db.query(UserConfig).filter(UserConfig.user_id == user_id).delete(
            synchronize_session=False
        )
        self.db.commit()
        return self.list_fields(user_id)

    def resolve_runtime(self, user_id: UUID) -> dict[str, Any]:
        resolved = {key: getattr(settings, key) for key in CONFIG_SPECS}
        rows = self.db.query(UserConfig).filter(UserConfig.user_id == user_id).all()
        for row in rows:
            if row.field_name in CONFIG_SPECS:
                resolved[row.field_name] = self._decode_row(row)
        return resolved

    def get_effective_value(self, user_id: UUID, field_name: str) -> Any:
        """Return the effective value for a single field: DB > env > default."""
        if field_name not in CONFIG_SPECS:
            raise ConfigurationError(f"Unknown configuration field: {field_name}")
        row = (
            self.db.query(UserConfig)
            .filter(UserConfig.user_id == user_id, UserConfig.field_name == field_name)
            .first()
        )
        if row is not None:
            return self._decode_row(row)
        return getattr(settings, field_name)

    def mask_secret(self, value: Any) -> str:
        """Mask a secret value for safe display. Public wrapper around _mask."""
        return self._mask(value)

    def encrypt_value(self, value: str) -> str:
        """Encrypt a value using Fernet. Returns the encrypted token as string."""
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt_value(self, token: str) -> str:
        """Decrypt a Fernet token. Raises ConfigurationError on failure."""
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError) as exc:
            raise ConfigurationError("Failed to decrypt configuration value") from exc

    @staticmethod
    def validate_encryption_key() -> None:
        """Validate the encryption key at startup. Logs warning if unset."""
        configured = settings.config_encryption_key.strip()
        if not configured:
            logger.warning(
                "SC_CONFIG_ENCRYPTION_KEY is not set. "
                "Encrypted config fields (ai_api_key, google_search_api_key, whisper_api_key) "
                "will use a key derived from JWT secret. "
                "Set SC_CONFIG_ENCRYPTION_KEY in .env for production use."
            )
            return
        try:
            Fernet(configured.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise ConfigurationError(
                "SC_CONFIG_ENCRYPTION_KEY is not a valid Fernet key. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            ) from exc

    def _decode_row(self, row: UserConfig) -> Any:
        raw = row.field_value
        if row.encrypted:
            try:
                raw = self._fernet.decrypt(raw.encode("ascii")).decode("utf-8")
            except (InvalidToken, ValueError) as exc:
                raise ConfigurationError(
                    f"Encrypted configuration field '{row.field_name}' cannot be decrypted"
                ) from exc
        return self._deserialize(raw, CONFIG_SPECS[row.field_name].value_type)

    def _fernet_key(self) -> bytes:
        configured = settings.config_encryption_key.strip()
        if configured:
            try:
                Fernet(configured.encode("ascii"))
                return configured.encode("ascii")
            except (ValueError, TypeError) as exc:
                raise ConfigurationError("SC_CONFIG_ENCRYPTION_KEY is not a valid Fernet key") from exc
        digest = hashlib.sha256(settings.jwt_secret_key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def _serialize(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def _deserialize(self, value: str, value_type: type) -> Any:
        decoded = json.loads(value)
        if value_type is float and isinstance(decoded, (int, float)):
            return float(decoded)
        if not isinstance(decoded, value_type):
            raise ConfigurationError("Stored configuration value has an invalid type")
        return decoded

    def _mask(self, value: Any) -> str:
        text = str(value or "")
        if not text:
            return ""
        if len(text) <= 8:
            return "••••••••"
        return f"{text[:4]}••••{text[-4:]}"

    def _looks_masked(self, value: Any) -> bool:
        return isinstance(value, str) and "••••" in value
