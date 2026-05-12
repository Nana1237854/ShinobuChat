from pathlib import Path
from typing import Any

from app.core.config import settings
from app.schemas.character import CharacterCard, CharacterCardOverride


class CharacterService:
    def __init__(self, characters_dir: Path | None = None):
        self.characters_dir = characters_dir or settings.characters_dir

    def load_for_user(self, user_id: str) -> CharacterCard:
        card = self.load_default()
        override_path = self._override_path(user_id)
        if not override_path.exists():
            return card
        try:
            import yaml
        except ModuleNotFoundError:
            return card
        data = yaml.safe_load(override_path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return card
        override = CharacterCardOverride.model_validate(self._clean_override_data(data))
        return self._merge_override(card, override)

    def load_default(self) -> CharacterCard:
        path = self.characters_dir / "shinobu.yaml"
        if not path.exists():
            return CharacterCard()
        try:
            import yaml
        except ModuleNotFoundError:
            return CharacterCard()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return CharacterCard()
        return CharacterCard.model_validate(self._clean_card_data(data))

    def _clean_card_data(self, data: dict[str, Any]) -> dict[str, Any]:
        allowed = {"name", "persona", "tone", "example_dialogue", "visual", "system_prompt_extra"}
        return {key: value for key, value in data.items() if key in allowed}

    def save_user_override(self, user_id: str, override: CharacterCardOverride) -> None:
        try:
            import yaml
        except ModuleNotFoundError:
            return
        self.characters_dir.mkdir(parents=True, exist_ok=True)
        data = override.model_dump(exclude_none=True)
        path = self._override_path(user_id)
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def _override_path(self, user_id: str) -> Path:
        safe = "".join(ch for ch in str(user_id) if ch.isalnum() or ch in {"-", "_"})
        return self.characters_dir / f"{safe or 'anonymous'}.yaml"

    def _clean_override_data(self, data: dict[str, Any]) -> dict[str, Any]:
        allowed = {"tone", "system_prompt_extra"}
        return {key: value for key, value in data.items() if key in allowed}

    def _merge_override(self, card: CharacterCard, override: CharacterCardOverride) -> CharacterCard:
        updates = {}
        if override.tone is not None:
            updates["tone"] = override.tone
        if override.system_prompt_extra is not None:
            updates["system_prompt_extra"] = override.system_prompt_extra
        return card.model_copy(update=updates)
