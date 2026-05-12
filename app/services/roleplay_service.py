import json

from app.core.config import settings
from app.core.context_manager import ContextManager
from app.schemas.character import ToneSettings
from app.skills.base import SkillError


class RoleplayService:
    async def generate_reply(
        self,
        user_message: str,
        context: ContextManager,
        tone: ToneSettings,
        extra: str = "",
    ) -> dict[str, str]:
        if not settings.effective_roleplay_api_key:
            return {
                "text": "I'm here! But my brain isn't fully connected yet.",
                "emotion": "thinking",
            }

        try:
            from openai import AsyncOpenAI
        except ModuleNotFoundError:
            return {
                "text": "I'm here! But my brain isn't fully connected yet.",
                "emotion": "thinking",
            }

        client = AsyncOpenAI(
            api_key=settings.effective_roleplay_api_key,
            base_url=settings.roleplay_llm_base_url or settings.llm_base_url,
        )
        messages = [
            {"role": "system", "content": context.roleplay_system_prompt(tone, extra)},
            *context.roleplay_slice(),
            {"role": "user", "content": user_message},
        ]
        try:
            response = await client.chat.completions.create(
                model=settings.roleplay_llm_model,
                messages=messages,
                temperature=settings.roleplay_llm_temperature,
                max_tokens=settings.roleplay_llm_max_tokens,
                response_format={"type": "json_object"},
            )
            payload = json.loads(response.choices[0].message.content or "{}")
            return {
                "text": str(payload.get("text") or "Hmm, I am here with you."),
                "emotion": str(payload.get("emotion") or "neutral"),
            }
        except Exception:
            return {
                "text": "Hmm, something in my thoughts snagged for a second. Could you try that again?",
                "emotion": "worried",
            }

    async def format_skill_result(
        self,
        skill_name: str,
        result: str,
        context: ContextManager,
        tone: ToneSettings,
    ) -> dict[str, str]:
        prompt = f"Skill '{skill_name}' finished with this result. Present it naturally to the user:\n{result}"
        return await self.generate_reply(prompt, context, tone)

    async def format_skill_error(
        self,
        error: SkillError,
        tone: ToneSettings,
        context: ContextManager,
    ) -> dict[str, str]:
        prompt = (
            f"A skill failed with code {error.code}. Message: {error.message}. "
            f"User-facing hint: {error.user_facing_hint}. Explain this naturally."
        )
        if not settings.effective_roleplay_api_key:
            return {"text": error.user_facing_hint, "emotion": "worried"}
        return await self.generate_reply(prompt, context, tone)
