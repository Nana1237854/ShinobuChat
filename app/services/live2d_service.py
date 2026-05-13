import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.exceptions import NotFoundError, UpstreamServiceError
from app.schemas.live2d import Live2DEmotionMapping, Live2DEmotionMappingItem, Live2DModelItem


class Live2DService:
    def __init__(self, live2d_dir: Path | None = None):
        self.live2d_dir = Path(live2d_dir or settings.live2d_assets_dir)

    def list_models(self) -> list[Live2DModelItem]:
        if not self.live2d_dir.exists():
            return []

        models: list[Live2DModelItem] = []
        for model_dir in sorted(self.live2d_dir.iterdir(), key=lambda item: item.name):
            if not model_dir.is_dir():
                continue
            record = self._read_model_record(model_dir)
            if record:
                models.append(Live2DModelItem.model_validate(record))
        return sorted(models, key=lambda item: item.name)

    def get_emotion_mapping(self, model_name: str) -> Live2DEmotionMapping:
        record = self._find_model_record(model_name)
        mapping = record.get("emotionMapping") or {}
        return {
            emotion: Live2DEmotionMappingItem.model_validate(item if isinstance(item, dict) else {})
            for emotion, item in mapping.items()
        }

    def save_emotion_mapping(
        self,
        model_name: str,
        emotion_mapping: Live2DEmotionMapping,
    ) -> Live2DEmotionMapping:
        model_dir, manifest = self._find_model_manifest(model_name)
        manifest["emotionMapping"] = {
            emotion: item.model_dump(exclude_none=True)
            for emotion, item in emotion_mapping.items()
        }
        manifest_path = model_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return emotion_mapping

    def _find_model_record(self, model_name: str) -> dict[str, Any]:
        for model_dir in self.live2d_dir.iterdir() if self.live2d_dir.exists() else []:
            if not model_dir.is_dir():
                continue
            record = self._read_model_record(model_dir)
            if not record:
                continue
            aliases = {model_dir.name, str(record["id"]), str(record["name"])}
            if model_name in aliases:
                return record
        raise NotFoundError("Live2D model not found")

    def _find_model_manifest(self, model_name: str) -> tuple[Path, dict[str, Any]]:
        for model_dir in self.live2d_dir.iterdir() if self.live2d_dir.exists() else []:
            if not model_dir.is_dir():
                continue
            manifest = self._read_manifest(model_dir)
            if not manifest:
                continue
            record = self._create_model_record(model_dir, manifest)
            aliases = {model_dir.name, str(record["id"]), str(record["name"])}
            if model_name in aliases:
                return model_dir, manifest
        raise NotFoundError("Live2D model not found")

    def _read_model_record(self, model_dir: Path) -> dict[str, Any] | None:
        manifest = self._read_manifest(model_dir)
        if manifest is None:
            manifest = self._infer_manifest(model_dir)
        if not manifest:
            return None
        return self._create_model_record(model_dir, manifest)

    def _read_manifest(self, model_dir: Path) -> dict[str, Any] | None:
        manifest_path = model_dir / "manifest.json"
        if not manifest_path.exists():
            return None
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as error:
            raise UpstreamServiceError(f"Failed to read Live2D manifest for {model_dir.name}: {error}") from error

    def _infer_manifest(self, model_dir: Path) -> dict[str, Any] | None:
        entry = sorted(model_dir.glob("*.model3.json"))
        if not entry:
            return None

        thumbnail = next(
            (
                file
                for file in model_dir.iterdir()
                if file.is_file() and file.name.lower() in {"icon.png", "icon.jpg", "thumbnail.png", "preview.png"}
            ),
            None,
        )
        manifest: dict[str, Any] = {"entry": entry[0].name}
        if thumbnail:
            manifest["thumbnail"] = thumbnail.name
        return manifest

    def _create_model_record(self, model_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
        entry = str(manifest["entry"])
        entry_name = Path(entry).name
        default_name = entry_name.removesuffix(".model3.json").removesuffix(".json") or model_dir.name

        record = {
            **manifest,
            "id": manifest.get("id") or model_dir.name,
            "name": manifest.get("name") or default_name,
            "entry": self._resolve_public_path(model_dir, entry),
        }
        if manifest.get("thumbnail"):
            record["thumbnail"] = self._resolve_public_path(model_dir, str(manifest["thumbnail"]))
        return record

    def _resolve_public_path(self, model_dir: Path, asset_path: str) -> str:
        if asset_path.startswith("/"):
            return asset_path
        resolved = (model_dir / asset_path).resolve()
        public_dir = self.live2d_dir.parents[1].resolve()
        return f"/{resolved.relative_to(public_dir).as_posix()}"
