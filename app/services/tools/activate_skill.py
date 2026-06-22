import json

from app.services.tool_registry import Tool, ToolContext


def create_tool(registry) -> Tool:
    def handler(arguments: dict, context: ToolContext) -> str:
        skill_name = str(arguments.get("name", ""))
        skill = context.user_skills.get(skill_name) or registry.skill_registry.get(skill_name)
        if not skill:
            return json.dumps({"error": f"Skill not found: {skill_name}"}, ensure_ascii=False)
        return skill.content

    return Tool(
        name="activate_skill",
        description="Load a local SKILL.md by skill name and return its instructions.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        handler=handler,
    )
