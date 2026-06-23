from __future__ import annotations

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
    "diary_enabled": ConfigSpec(bool),
    "auto_diary_enabled": ConfigSpec(bool),
    "auto_diary_timezone": ConfigSpec(str),
}


class ConfigService:
    def __init__(self, db: Session):
        self.db = db
        key = self._fernet_key()
        self._fernet = Fernet(key) if key else None
        self._encryption_available = key is not None

    def list_fields(self, user_id: UUID) -> UserConfigOut:
        rows = {
            row.field_name: row
            for row in self.db.query(UserConfig).filter(UserConfig.user_id == user_id).all()
        }
        fields: list[UserConfigFieldOut] = []
        for key, spec in CONFIG_SPECS.items():
            row = rows.get(key)
            if row is not None:
                value = self._decode_row_display(row)
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
            if spec.encrypted and not self._encryption_available:
                raise ConfigurationError(
                    f"Cannot save encrypted field '{key}': "
                    "SC_CONFIG_ENCRYPTION_KEY is not set. "
                    "Configure a Fernet key in .env to enable saving API keys."
                )
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
                resolved[row.field_name] = self._decode_row_runtime(row)
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
            return self._decode_row_runtime(row)
        return getattr(settings, field_name)

    def mask_secret(self, value: Any) -> str:
        """Mask a secret value for safe display. Public wrapper around _mask."""
        return self._mask(value)

    def encrypt_value(self, value: str) -> str:
        """Encrypt a value using Fernet. Raises if key is not available."""
        if not self._encryption_available:
            raise ConfigurationError(
                "Cannot encrypt: SC_CONFIG_ENCRYPTION_KEY is not set."
            )
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt_value(self, token: str) -> str:
        """Decrypt a Fernet token. Raises ConfigurationError on failure."""
        if not self._encryption_available:
            raise ConfigurationError(
                "Cannot decrypt: SC_CONFIG_ENCRYPTION_KEY is not set."
            )
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError) as exc:
            raise ConfigurationError("Failed to decrypt configuration value") from exc

    @staticmethod
    def validate_encryption_key() -> None:
        """Validate the encryption key at startup.

        Warns if SC_CONFIG_ENCRYPTION_KEY is unset. Encrypted field reads/writes
        will be blocked until a valid key is configured. Raises ConfigurationError
        only if the configured key has an invalid format.
        """
        configured = settings.config_encryption_key.strip()
        if not configured:
            logger.warning(
                "SC_CONFIG_ENCRYPTION_KEY is not set. "
                "Encrypted config fields (ai_api_key, google_search_api_key, whisper_api_key) "
                "cannot be saved until a key is configured. "
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
        """Decode a config row. Falls back to mask when encryption key is unavailable.

        Prefer _decode_row_runtime() or _decode_row_display() for call-site clarity.
        """
        raw = row.field_value
        if row.encrypted:
            if not self._encryption_available:
                return "••••••••"
            try:
                raw = self._fernet.decrypt(raw.encode("ascii")).decode("utf-8")
            except (InvalidToken, ValueError) as exc:
                raise ConfigurationError(
                    f"Encrypted configuration field '{row.field_name}' cannot be decrypted"
                ) from exc
        return self._deserialize(raw, CONFIG_SPECS[row.field_name].value_type)

    def _decode_row_runtime(self, row: UserConfig) -> Any:
        """Decode for runtime use (resolve_runtime, get_effective_value).

        Raises ConfigurationError if an encrypted field exists but the encryption
        key is unavailable — must never return a mask that would be used as a real key.
        """
        if row.encrypted and not self._encryption_available:
            raise ConfigurationError(
                f"Cannot read encrypted field '{row.field_name}': "
                "SC_CONFIG_ENCRYPTION_KEY is not set. "
                "Configure a Fernet key in .env to access stored API keys."
            )
        return self._decode_row(row)

    def _decode_row_display(self, row: UserConfig) -> Any:
        """Decode for frontend display (list_fields).

        Safe to return a mask when encryption key is unavailable — the frontend
        shows masks for encrypted fields anyway.
        """
        return self._decode_row(row)

    def _fernet_key(self) -> bytes | None:
        """Return the Fernet key bytes, or None if not configured.

        Never derives from JWT secret — encrypted fields require an explicit key.
        """
        configured = settings.config_encryption_key.strip()
        if not configured:
            return None
        try:
            Fernet(configured.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise ConfigurationError("SC_CONFIG_ENCRYPTION_KEY is not a valid Fernet key") from exc
        return configured.encode("ascii")

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
