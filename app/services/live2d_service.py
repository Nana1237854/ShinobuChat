import json
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status


SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class Live2DAssetService:
    def __init__(self, frontend_dist: Path) -> None:
        self.frontend_dist = frontend_dist
        self.live2d_dir = frontend_dist / "assets" / "live2d"

    def manifest(self) -> dict[str, list[dict[str, Any]]]:
        if not self.live2d_dir.exists():
            return {"models": []}

        models = [
            model
            for model_dir in sorted(self.live2d_dir.iterdir(), key=lambda item: item.name.casefold())
            if model_dir.is_dir()
            for model in [self._discover_model(model_dir)]
            if model is not None
        ]
        return {"models": models}

    async def import_zip(self, file: UploadFile) -> dict[str, Any]:
        if not file.filename or not file.filename.lower().endswith(".zip"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a Live2D zip file")

        data = await file.read()
        if not data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded zip is empty")

        import io

        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid zip file") from exc

        members = [member for member in archive.infolist() if not member.is_dir()]
        model_members = [member for member in members if member.filename.lower().endswith(".model3.json")]
        if not model_members:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No .model3.json file found in zip")

        model_member = self._pick_model_member(model_members)
        package_root = self._package_root(model_member.filename)
        target_name = self._safe_model_dir_name(package_root or Path(file.filename).stem)
        target_dir = self.live2d_dir / target_name
        if target_dir.exists():
            target_dir = self.live2d_dir / f"{target_name}-{uuid.uuid4().hex[:8]}"

        target_dir.mkdir(parents=True, exist_ok=False)
        for member in members:
            relative_name = self._relative_member_name(member.filename, package_root)
            if not relative_name:
                continue
            target = (target_dir / relative_name).resolve()
            if not self._is_relative_to(target, target_dir.resolve()):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Zip contains unsafe paths")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))

        model = self._discover_model(target_dir)
        if model is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Imported files are not a valid Live2D model")

        self._write_sub_manifest(target_dir, model)
        return {"model": model, "models": self.manifest()["models"]}

    def _discover_model(self, model_dir: Path) -> dict[str, Any] | None:
        manifest = self._read_sub_manifest(model_dir)
        model_file = self._find_model_file(model_dir, manifest.get("entry"))
        if not model_file:
            return None

        thumbnail = manifest.get("thumbnail") or self._find_thumbnail(model_dir)
        model = {
            "id": str(manifest.get("id") or self._safe_model_id(model_dir.name)),
            "name": str(manifest.get("name") or model_file.stem.replace(".model3", "")),
            "entry": str(manifest.get("entry") or self._asset_path(model_file)),
        }
        if thumbnail:
            model["thumbnail"] = str(thumbnail)

        for key, default in (("defaultScale", 0.32), ("defaultX", 52), ("defaultY", 76)):
            model[key] = manifest.get(key, default)

        return model

    def _read_sub_manifest(self, model_dir: Path) -> dict[str, Any]:
        manifest_file = model_dir / "manifest.json"
        if not manifest_file.exists():
            return {}
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _find_model_file(self, model_dir: Path, manifest_entry: object) -> Path | None:
        if isinstance(manifest_entry, str) and manifest_entry:
            candidate = self._resolve_asset_url(manifest_entry)
            if candidate and candidate.exists():
                return candidate
        return next(model_dir.rglob("*.model3.json"), None)

    def _find_thumbnail(self, model_dir: Path) -> str | None:
        for pattern in ("preview.*", "icon*.*", "*.png", "*.jpg", "*.jpeg", "*.webp"):
            thumbnail = next(model_dir.rglob(pattern), None)
            if thumbnail:
                return self._asset_path(thumbnail)
        return None

    def _write_sub_manifest(self, model_dir: Path, model: dict[str, Any]) -> None:
        manifest_file = model_dir / "manifest.json"
        manifest_file.write_text(
            json.dumps(model, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _asset_path(self, path: Path) -> str:
        return "/" + path.relative_to(self.frontend_dist).as_posix()

    def _resolve_asset_url(self, url: str) -> Path | None:
        if not url.startswith("/assets/"):
            return None
        return (self.frontend_dist / url.removeprefix("/")).resolve()

    def _safe_model_id(self, value: str) -> str:
        clean = SAFE_NAME_PATTERN.sub("-", value.strip()).strip("-._")
        return clean or f"live2d-{uuid.uuid4().hex[:8]}"

    def _safe_model_dir_name(self, value: str) -> str:
        return self._safe_model_id(Path(value).name)

    def _pick_model_member(self, members: list[zipfile.ZipInfo]) -> zipfile.ZipInfo:
        return min(members, key=lambda member: (member.filename.count("/"), member.filename.lower()))

    def _package_root(self, filename: str) -> str:
        parts = Path(filename.replace("\\", "/")).parts
        return parts[0] if len(parts) > 1 else ""

    def _relative_member_name(self, filename: str, package_root: str) -> Path | None:
        clean = filename.replace("\\", "/").lstrip("/")
        if package_root and clean.startswith(f"{package_root}/"):
            clean = clean[len(package_root) + 1 :]
        if not clean or clean.endswith("/"):
            return None
        return Path(clean)

    def _is_relative_to(self, path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
        except ValueError:
            return False
        return True
