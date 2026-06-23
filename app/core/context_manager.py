from app.models.message import Message
from app.schemas.character import CharacterCard, ToneSettings


class ContextManager:
    def __init__(self, messages: list[Message], character_card: CharacterCard | None = None):
        self.messages = messages
        self.character_card = character_card or CharacterCard()

    def decision_slice(self, max_messages: int = 10) -> list[dict[str, str]]:
        messages = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        return [{"role": message.role, "content": message.content[:200]} for message in messages]

    def decision_system_prompt(self, skills_text: str, mode_instruction: str = "") -> str:
        base = (
            "You are an intent router. Analyze the user's message and decide:\n"
            "- route='chat': casual conversation, no action needed\n"
            "- route='agent': user wants a specific task done\n\n"
            "Available skills:\n"
            f"{skills_text}\n\n"
            "Respond with JSON: {\"route\": \"chat\"|\"agent\", \"skill_name\": null|string, "
            "\"skill_params\": {}, \"reasoning\": \"...\", \"confidence\": 0.0-1.0}\n"
            "Rules:\n"
            "- If intent is unclear or no skill matches, use route='chat' and confidence<0.6\n"
            "- Only set skill_name if a specific skill clearly matches"
        )
        if mode_instruction:
            base += f"\n\n{mode_instruction}"
        return base

    def roleplay_slice(self, max_messages: int = 30) -> list[dict[str, str]]:
        messages = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        return [
            {"role": "assistant" if message.role == "assistant" else "user", "content": message.content}
            for message in messages
        ]

    def roleplay_system_prompt(
        self, tone: ToneSettings, extra: str = "", mode_section: str = ""
    ) -> str:
        card = self.character_card
        parts = [
            f"You are {card.name}. {card.persona}",
            f"Tone - warmth: {tone.warmth:.1f}, sharpness: {tone.sharpness:.1f}, formality: {tone.formality:.1f}",
        ]
        if card.example_dialogue:
            parts.append("Example responses:\n" + "\n".join(f"- {dialogue}" for dialogue in card.example_dialogue))
        if mode_section:
            parts.append(mode_section)
        if extra:
            parts.append(f"Additional instructions: {extra}")
        parts.append(
            'Respond with JSON: {"text": "your reply", "emotion": "happy|neutral|surprised|worried|sad|thinking"}'
        )
        return "\n\n".join(parts)
