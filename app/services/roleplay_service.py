import json

from app.core.config import settings
from app.core.context_manager import ContextManager
from app.schemas.character import ToneSettings
from app.skills.base import SkillError


ERROR_HINTS = {
    "TIMEOUT": "比预期久了一些... 要不要再试一次？",
    "PERMISSION_DENIED": "这个操作我没有权限呢。你能帮我检查一下设置吗？",
    "NETWORK_ERROR": "网络好像不太稳定，稍后再试？",
    "API_KEY_MISSING": "这个功能还没配置好，需要先设置 API Key 哦。",
    "OCR_NOT_AVAILABLE": "OCR 组件没装上，暂时读不了屏幕内容。",
    "SKILL_NOT_FOUND": "我还没学会这个技能呢。",
    "PIPELINE_ERROR": "内部出了点小问题，再试一次？",
    "INVALID_PARAMS": "参数看起来不太对，我们换个说法再试一次？",
    "CANCELLED": "好的，这次操作已经取消。",
    "UNKNOWN": "出了点小问题，再试一次？",
}


class RoleplayService:
    async def generate_reply(
        self,
        user_message: str,
        context: ContextManager,
        tone: ToneSettings,
        extra: str = "",
        mode_section: str = "",
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
            {"role": "system", "content": context.roleplay_system_prompt(tone, extra, mode_section)},
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
        hint = ERROR_HINTS.get(error.code, error.user_facing_hint or ERROR_HINTS["UNKNOWN"])
        prompt = (
            f"[System: A task failed with error '{error.code}'. "
            f"Internal message: {error.message}. "
            f"Tell the user naturally: {hint}. Output JSON with text and emotion='worried'.]"
        )
        if not settings.effective_roleplay_api_key:
            return {"text": hint, "emotion": "worried"}
        return await self.generate_reply(prompt, context, tone)
