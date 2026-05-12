from pathlib import Path
from typing import Any

from app.core.config import settings
from app.schemas.character import CharacterCard


class CharacterService:
    def __init__(self, characters_dir: Path | None = None):
        self.characters_dir = characters_dir or settings.characters_dir

    def load_for_user(self, user_id: str) -> CharacterCard:
        del user_id
        return self.load_default()

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
