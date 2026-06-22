from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from app.services.tool_registry import ToolContext


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    reason: str
    tool_name: str = ""
    checked_fields: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.passed


class ToolVerifier:
    def __init__(
        self,
        session_factory: Callable[[], Any] | None = None,
    ):
        self._session_factory = session_factory

    def verify(
        self,
        tool_name: str,
        result: str,
        arguments: dict,
        context: "ToolContext",
    ) -> VerificationResult:
        checked: dict[str, Any] = {}

        normalized = (result or "").strip()
        checked["result_empty"] = not bool(normalized)
        if not normalized:
            return VerificationResult(
                False,
                "tool returned an empty result",
                tool_name=tool_name,
                checked_fields=checked,
            )

        # Explicit ERROR: prefix check
        checked["starts_with_error"] = normalized.startswith("ERROR:")
        if normalized.startswith("ERROR:"):
            return VerificationResult(
                False,
                "tool result begins with ERROR:",
                tool_name=tool_name,
                checked_fields=checked,
            )

        # JSON error payload check
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError:
            payload = None
        checked["is_json"] = payload is not None
        if isinstance(payload, dict) and (payload.get("error") or payload.get("status") == "error"):
            return VerificationResult(
                False,
                "tool returned an error payload",
                tool_name=tool_name,
                checked_fields=checked,
            )

        # Failure keyword markers
        lowered = normalized.lower()
        failure_markers = (
            "failed",
            "timed out",
            "rejected:",
            "not found",
            "unknown tool",
        )
        checked["has_failure_marker"] = any(marker in lowered for marker in failure_markers)
        if checked["has_failure_marker"]:
            return VerificationResult(
                False,
                "tool result contains an explicit failure keyword",
                tool_name=tool_name,
                checked_fields=checked,
            )

        # Dispatch to tool-specific verifier
        checker_name = _TOOL_CHECKERS.get(tool_name)
        if checker_name is not None:
            specific_result = getattr(self, checker_name)(result, arguments, context)
            checked.update(specific_result.checked_fields)
            if not specific_result.passed:
                return VerificationResult(
                    False,
                    specific_result.reason,
                    tool_name=tool_name,
                    checked_fields=checked,
                )
            return VerificationResult(
                True,
                specific_result.reason,
                tool_name=tool_name,
                checked_fields=checked,
            )

        checked["generic_passed"] = True
        return VerificationResult(
            True,
            "verification passed",
            tool_name=tool_name,
            checked_fields=checked,
        )

    # --- Tool-specific checkers ---

    def _check_shell_command(
        self, result: str, arguments: dict, context: "ToolContext"
    ) -> VerificationResult:
        exit_code = context.metadata.get("exit_code")
        checked = {"exit_code": exit_code}
        if exit_code is None:
            return VerificationResult(
                False,
                "shell command did not report an exit code",
                tool_name="shell_command",
                checked_fields=checked,
            )
        if exit_code != 0:
            return VerificationResult(
                False,
                f"shell command exited with code {exit_code}",
                tool_name="shell_command",
                checked_fields=checked,
            )
        return VerificationResult(
            True,
            "shell exit code is 0",
            tool_name="shell_command",
            checked_fields=checked,
        )

    def _check_write_file(
        self, result: str, arguments: dict, context: "ToolContext"
    ) -> VerificationResult:
        file_path = arguments.get("file_path") or arguments.get("path") or ""
        checked = {"file_path": file_path}
        if not file_path:
            return VerificationResult(
                False,
                "write_file: no file_path in arguments",
                tool_name="write_file",
                checked_fields=checked,
            )
        target = Path(file_path)
        exists = target.exists()
        checked["file_exists"] = exists
        if not exists:
            return VerificationResult(
                False,
                f"write_file: target file does not exist at {file_path}",
                tool_name="write_file",
                checked_fields=checked,
            )
        return VerificationResult(
            True,
            f"file exists at {file_path}",
            tool_name="write_file",
            checked_fields=checked,
        )

    def _check_edit_file(
        self, result: str, arguments: dict, context: "ToolContext"
    ) -> VerificationResult:
        return self._check_write_file(result, arguments, context)

    def _check_todo_create(
        self, result: str, arguments: dict, context: "ToolContext"
    ) -> VerificationResult:
        checked: dict[str, Any] = {}
        todo_id = None

        # Try parsing result as JSON for todo id
        try:
            payload = json.loads(result)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            todo_id = payload.get("id") or payload.get("todo_id")
        checked["result_has_todo_id"] = bool(todo_id)

        # Validate UUID format
        if todo_id:
            try:
                uuid.UUID(str(todo_id))
                checked["todo_id_valid_uuid"] = True
            except (ValueError, AttributeError):
                checked["todo_id_valid_uuid"] = False
                todo_id = None

        # DB verification if available
        if todo_id and self._session_factory:
            try:
                from app.models.todo import Todo

                db = self._session_factory()
                exists = (
                    db.query(Todo).filter(Todo.id == todo_id).first() is not None
                )
                checked["todo_in_db"] = exists
                db.close()
            except Exception:
                checked["todo_in_db"] = "check_failed"

        if not todo_id:
            return VerificationResult(
                False,
                "todo_create: no valid todo id found in result",
                tool_name="todo_create",
                checked_fields=checked,
            )
        return VerificationResult(
            True,
            f"todo_create: todo id {todo_id} found",
            tool_name="todo_create",
            checked_fields=checked,
        )

    def _check_memory_store(
        self, result: str, arguments: dict, context: "ToolContext"
    ) -> VerificationResult:
        checked: dict[str, Any] = {}
        memory_id = None

        try:
            payload = json.loads(result)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            memory_id = payload.get("id") or payload.get("memory_id")
        checked["result_has_memory_id"] = bool(memory_id)

        if memory_id:
            try:
                uuid.UUID(str(memory_id))
                checked["memory_id_valid_uuid"] = True
            except (ValueError, AttributeError):
                checked["memory_id_valid_uuid"] = False
                memory_id = None

        if memory_id and self._session_factory:
            try:
                from app.models.memory import Memory

                db = self._session_factory()
                exists = (
                    db.query(Memory).filter(Memory.id == memory_id).first() is not None
                )
                checked["memory_in_db"] = exists
                db.close()
            except Exception:
                checked["memory_in_db"] = "check_failed"

        if not memory_id:
            return VerificationResult(
                False,
                "memory_store: no valid memory id found in result",
                tool_name="memory_store",
                checked_fields=checked,
            )
        return VerificationResult(
            True,
            f"memory_store: memory id {memory_id} found",
            tool_name="memory_store",
            checked_fields=checked,
        )

    def _check_skill_install(
        self, result: str, arguments: dict, context: "ToolContext"
    ) -> VerificationResult:
        checked: dict[str, Any] = {}
        skill_name = arguments.get("name") or arguments.get("skill_name") or ""

        # Try from result payload first
        try:
            payload = json.loads(result)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            skill_name = skill_name or payload.get("name") or payload.get("skill_name") or ""

        checked["skill_name"] = skill_name
        if not skill_name:
            return VerificationResult(
                False,
                "skill_install: no skill name in arguments or result",
                tool_name="skill_install",
                checked_fields=checked,
            )

        # Check user_skills in context
        if skill_name in context.user_skills:
            checked["skill_in_user_context"] = True
            return VerificationResult(
                True,
                f"skill_install: skill '{skill_name}' found in context",
                tool_name="skill_install",
                checked_fields=checked,
            )

        checked["skill_in_user_context"] = False

        # Check DB if available
        if self._session_factory:
            try:
                from app.models.user_skill import UserSkill

                db = self._session_factory()
                exists = (
                    db.query(UserSkill)
                    .filter(UserSkill.name == skill_name)
                    .first()
                    is not None
                )
                checked["skill_in_db"] = exists
                db.close()
                if exists:
                    return VerificationResult(
                        True,
                        f"skill_install: skill '{skill_name}' found in DB",
                        tool_name="skill_install",
                        checked_fields=checked,
                    )
            except Exception:
                checked["skill_in_db"] = "check_failed"

        return VerificationResult(
            False,
            f"skill_install: skill '{skill_name}' not found in registry or DB",
            tool_name="skill_install",
            checked_fields=checked,
        )

    def _check_config_update(
        self, result: str, arguments: dict, context: "ToolContext"
    ) -> VerificationResult:
        checked: dict[str, Any] = {}
        config_key = arguments.get("key") or arguments.get("field_name") or ""
        config_value = arguments.get("value")

        checked["config_key"] = config_key
        checked["config_value_provided"] = config_value is not None

        if not config_key:
            return VerificationResult(
                False,
                "config_update: no config key in arguments",
                tool_name="config_update",
                checked_fields=checked,
            )

        # Parse result to see if it reports success
        try:
            payload = json.loads(result)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            checked["result_has_key"] = config_key in payload.get("fields", {}) or payload.get("key") == config_key

        # Re-read from DB if available
        if self._session_factory and config_key:
            try:
                from app.models.user_config import UserConfig

                db = self._session_factory()
                row = (
                    db.query(UserConfig)
                    .filter(UserConfig.field_name == config_key)
                    .first()
                )
                if row is not None:
                    checked["config_row_exists"] = True
                    checked["config_row_value_present"] = bool(row.field_value)
                else:
                    checked["config_row_exists"] = False
                db.close()
            except Exception:
                checked["config_db_check"] = "check_failed"

        # If we couldn't re-read, but result doesn't indicate error, treat as soft pass
        if "config_row_exists" not in checked:
            checked["re_read_performed"] = False
            if isinstance(payload, dict) and not payload.get("error"):
                return VerificationResult(
                    True,
                    f"config_update: result accepted for key '{config_key}' (re-read not available)",
                    tool_name="config_update",
                    checked_fields=checked,
                )

        if checked.get("config_row_exists") is True:
            return VerificationResult(
                True,
                f"config_update: key '{config_key}' re-read confirmed in DB",
                tool_name="config_update",
                checked_fields=checked,
            )

        return VerificationResult(
            False,
            f"config_update: could not confirm key '{config_key}' in DB after update",
            tool_name="config_update",
            checked_fields=checked,
        )


# Registry of tool-specific checkers
_TOOL_CHECKERS: dict[str, str] = {
    "shell_command": "_check_shell_command",
    "write_file": "_check_write_file",
    "edit_file": "_check_edit_file",
    "todo_create": "_check_todo_create",
    "memory_store": "_check_memory_store",
    "skill_install": "_check_skill_install",
    "config_update": "_check_config_update",
}
