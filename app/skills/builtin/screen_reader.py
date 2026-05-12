from pydantic import BaseModel

from app.skills.base import CancelToken, OnProgress, Skill, SkillError, SkillProgress


class ScreenReaderParams(BaseModel):
    user_id: str = ""
    region: str = "full"


class ScreenReaderSkill(Skill):
    name = "screen_reader"
    description = "截取当前屏幕并用 OCR 识别文字内容"
    parameters = ScreenReaderParams
    example_triggers = ["看看屏幕", "读取屏幕", "我在看什么", "帮我看看这个页面", "屏幕上有啥", "识别屏幕"]

    async def execute(
        self,
        params: dict,
        on_progress: OnProgress,
        timeout: float,
        cancel_token: CancelToken,
    ) -> str:
        del params, timeout
        try:
            from PIL import ImageGrab
        except ImportError as exc:
            raise SkillError("OCR_NOT_AVAILABLE", "Pillow not installed", "截图组件没装上，暂时读不了屏幕内容。") from exc

        try:
            import easyocr
        except ImportError as exc:
            raise SkillError("OCR_NOT_AVAILABLE", "easyocr not installed", "OCR 组件没装上，暂时读不了屏幕内容。") from exc

        await on_progress(SkillProgress(skill_name=self.name, message="截取屏幕...", percent=0.15))
        image = ImageGrab.grab()
        if cancel_token.is_set():
            raise SkillError("CANCELLED", "Skill cancelled", "屏幕读取已取消。")

        await on_progress(SkillProgress(skill_name=self.name, message="识别文字中...", percent=0.35))
        reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
        results = reader.readtext(image)

        await on_progress(SkillProgress(skill_name=self.name, message="整理结果...", percent=0.85))
        if not results:
            return "屏幕上没识别到文字。"

        results.sort(key=lambda result: (result[0][0][1], result[0][0][0]))
        lines = ["# 屏幕文字识别结果", ""]
        for _, text, _ in results:
            clean = str(text).strip()
            if len(clean) <= 1 and not clean.isalnum():
                continue
            lines.append(clean)
        return "\n".join(lines) if len(lines) > 2 else "屏幕上没识别到可用文字。"
