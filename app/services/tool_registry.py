from __future__ import annotations

import importlib
import json
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass

from app.models.message import Message
from app.services.http_client import UrllibHttpClient
from app.services.skill_service import SkillRegistry


@dataclass(frozen=True)
class ToolContext:
    history: list[Message]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[[dict, ToolContext], str]

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self, skill_registry: SkillRegistry, http_client: UrllibHttpClient | None = None):
        self.skill_registry = skill_registry
        self.http_client = http_client or UrllibHttpClient()
        self._tools = {tool.name: tool for tool in self._load_tools()}

    def _load_tools(self) -> list[Tool]:
        package_name = "app.services.tools"
        package = importlib.import_module(package_name)
        tools: list[Tool] = []
        for module_info in pkgutil.iter_modules(package.__path__, f"{package_name}."):
            module = importlib.import_module(module_info.name)
            create_tool = getattr(module, "create_tool", None)
            if create_tool is not None:
                tools.append(create_tool(self))
        return tools

    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict, context: ToolContext) -> str:
        tool = self._tools.get(name)
        if not tool:
            return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
        return tool.handler(arguments, context)
