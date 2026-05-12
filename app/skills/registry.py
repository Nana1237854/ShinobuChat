import importlib
import pkgutil

from app.skills.base import Skill


class SkillRegistry:
    _skills: dict[str, Skill] = {}

    @classmethod
    def discover(cls) -> None:
        try:
            import app.skills.builtin as builtin_pkg

            for _, name, _ in pkgutil.iter_modules(builtin_pkg.__path__):
                module = importlib.import_module(f"app.skills.builtin.{name}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, Skill) and attr is not Skill:
                        instance = attr()
                        cls._skills[instance.name] = instance
        except ModuleNotFoundError:
            pass

    @classmethod
    def get(cls, name: str) -> Skill | None:
        return cls._skills.get(name)

    @classmethod
    def list_skills(cls) -> list[Skill]:
        return list(cls._skills.values())

    @classmethod
    def describe_for_llm(cls) -> str:
        if not cls._skills:
            return "No skills available."
        lines = []
        for skill in cls._skills.values():
            triggers = ", ".join(f'"{trigger}"' for trigger in skill.example_triggers[:3])
            lines.append(f"- {skill.name}: {skill.description}")
            if triggers:
                lines.append(f"  Trigger examples: {triggers}")
        return "\n".join(lines)


SkillRegistry.discover()
