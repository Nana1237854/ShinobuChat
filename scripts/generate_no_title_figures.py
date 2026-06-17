from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUT = Path(r"D:\ShinobuChat\output\course_paper_assets\no_title")
OUT.mkdir(parents=True, exist_ok=True)
FONT_HEI = Path(r"C:\Windows\Fonts\simhei.ttf")


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines: list[str] = []
    for raw in text.splitlines():
        if not raw:
            lines.append("")
            continue
        line = ""
        for ch in raw:
            trial = line + ch
            width = draw.textbbox((0, 0), trial, font=font)[2]
            if width <= max_width or not line:
                line = trial
            else:
                lines.append(line)
                line = ch
        if line:
            lines.append(line)
    return lines


def draw_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], text: str, font, fill: str):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=18, fill=fill, outline="#2F3A4A", width=2)
    lines = wrap_text(text, font, x2 - x1 - 24)
    total_h = len(lines) * 28
    y = y1 + (y2 - y1 - total_h) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        draw.text((x1 + (x2 - x1 - (bbox[2] - bbox[0])) // 2, y), line, font=font, fill="#111827")
        y += 28


def draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color="#374151"):
    draw.line([start, end], fill=color, width=4)
    ex, ey = end
    sx, sy = start
    if abs(ex - sx) >= abs(ey - sy):
        direction = 1 if ex > sx else -1
        pts = [(ex, ey), (ex - direction * 18, ey - 10), (ex - direction * 18, ey + 10)]
    else:
        direction = 1 if ey > sy else -1
        pts = [(ex, ey), (ex - 10, ey - direction * 18), (ex + 10, ey - direction * 18)]
    draw.polygon(pts, fill=color)


def shift_xy(xy: tuple[int, int, int, int], dy=-95) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = xy
    return (x1, y1 + dy, x2, y2 + dy)


def shift_pt(pt: tuple[int, int], dy=-95) -> tuple[int, int]:
    x, y = pt
    return (x, y + dy)


def save_diagram(
    path: Path,
    boxes: list[tuple[str, tuple[int, int, int, int], str]],
    arrows: list[tuple[tuple[int, int], tuple[int, int]]],
    *,
    height: int = 680,
):
    img = Image.new("RGB", (1500, height), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    box_font = ImageFont.truetype(str(FONT_HEI), 25)
    for text, xy, fill in boxes:
        draw_box(draw, shift_xy(xy), text, box_font, fill)
    for start, end in arrows:
        draw_arrow(draw, shift_pt(start), shift_pt(end))
    img.save(path)


def main():
    save_diagram(
        OUT / "fig3-1-progressive-no-title.png",
        [
            ("L1 基础对话\nLLM API + SSE", (55, 190, 275, 315), "#E8F3FF"),
            ("L2 语音交互\nASR + Edge-TTS", (300, 190, 520, 315), "#EEF8E8"),
            ("L3 视觉表达\nLive2D + 口型", (545, 190, 765, 315), "#FFF4DB"),
            ("L4 工具调用\nToolRegistry + Skills", (790, 190, 1040, 315), "#F4EAFE"),
            ("L5 长期记忆\npgvector + Embedding", (1065, 190, 1325, 315), "#FFECEC"),
            ("L6 多 Agent\nRouter/Chat/Task/Memory", (520, 455, 980, 585), "#EAF5F5"),
        ],
        [((275, 252), (300, 252)), ((520, 252), (545, 252)), ((765, 252), (790, 252)), ((1040, 252), (1065, 252)), ((1195, 315), (805, 455))],
    )

    save_diagram(
        OUT / "fig3-2-intent-security-no-title.png",
        [
            ("用户自然语言输入", (90, 170, 350, 270), "#E8F3FF"),
            ("L1 规则/关键词\nRouterAgent 快速分类", (430, 110, 735, 220), "#EEF8E8"),
            ("L2 AI 语义判断\nChat / Agent / Auto", (430, 255, 735, 365), "#FFF4DB"),
            ("L3 LLM 深度推理\n生成回复或工具计划", (430, 400, 735, 510), "#F4EAFE"),
            ("内层：Prompt 行为约束", (845, 175, 1160, 275), "#FFECEC"),
            ("外层：工具沙箱\ncurl / http(s) / skills 白名单", (845, 355, 1210, 470), "#EAF5F5"),
            ("聊天 / 工具 / 语音 / Live2D 输出", (535, 590, 1025, 690), "#F2F4F7"),
        ],
        [((350, 220), (430, 165)), ((585, 220), (585, 255)), ((585, 365), (585, 400)), ((735, 455), (845, 225)), ((1010, 275), (1010, 355)), ((1010, 470), (840, 590)), ((585, 510), (660, 590))],
        height=700,
    )

    save_diagram(
        OUT / "fig3-3-memory-rag-no-title.png",
        [
            ("本轮用户消息", (80, 170, 320, 270), "#E8F3FF"),
            ("Embedding 向量化", (410, 170, 670, 270), "#EEF8E8"),
            ("pgvector Top-K 检索", (760, 170, 1050, 270), "#FFF4DB"),
            ("记忆注入 Prompt", (1140, 170, 1390, 270), "#F4EAFE"),
            ("LLM 生成个性化回复", (470, 430, 790, 540), "#FFECEC"),
            ("MemoryAgent 异步提取稳定事实", (860, 430, 1255, 540), "#EAF5F5"),
            ("memories 表\ncontent / embedding / importance", (520, 600, 1110, 700), "#F2F4F7"),
        ],
        [((320, 220), (410, 220)), ((670, 220), (760, 220)), ((1050, 220), (1140, 220)), ((1265, 270), (710, 430)), ((790, 485), (860, 485)), ((1060, 540), (865, 600)), ((720, 600), (555, 540))],
        height=710,
    )

    save_diagram(
        OUT / "fig4-1-data-flow-no-title.png",
        [
            ("React 前端\n文本/语音输入", (70, 160, 335, 280), "#E8F3FF"),
            ("FastAPI MessageService\n会话、路由、SSE", (430, 160, 760, 280), "#EEF8E8"),
            ("DeepSeek LLM\n回复与 emotion 标签", (855, 110, 1185, 220), "#FFF4DB"),
            ("Edge-TTS / ASR\n语音链路", (855, 270, 1185, 380), "#F4EAFE"),
            ("PostgreSQL / pgvector\n消息、记忆、会话", (855, 430, 1215, 540), "#FFECEC"),
            ("前端播放与表现\n文字、音频、Live2D", (440, 580, 830, 690), "#EAF5F5"),
        ],
        [((335, 220), (430, 220)), ((760, 190), (855, 165)), ((760, 230), (855, 325)), ((760, 260), (855, 485)), ((1015, 220), (650, 580)), ((1015, 380), (710, 580)), ((1015, 540), (770, 580))],
        height=700,
    )

    save_diagram(
        OUT / "fig4-2-iteration-no-title.png",
        [
            ("原型\nLive Room 与路由设想", (75, 190, 330, 310), "#E8F3FF"),
            ("MVP\nFastAPI + React + SSE", (400, 190, 655, 310), "#EEF8E8"),
            ("多模态\nTTS/ASR + Live2D", (725, 190, 980, 310), "#FFF4DB"),
            ("Agent\nToolRegistry + Skills", (1050, 190, 1325, 310), "#F4EAFE"),
            ("增强\n记忆 + 多 Agent + 测试", (520, 475, 970, 595), "#FFECEC"),
        ],
        [((330, 250), (400, 250)), ((655, 250), (725, 250)), ((980, 250), (1050, 250)), ((1190, 310), (810, 475))],
    )

    print(OUT)


if __name__ == "__main__":
    main()
