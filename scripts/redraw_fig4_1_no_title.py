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


def draw_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], text: str, font, fill: str) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=18, fill=fill, outline="#2F3A4A", width=2)
    lines = wrap_text(text, font, x2 - x1 - 30)
    total_h = len(lines) * 31
    y = y1 + (y2 - y1 - total_h) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        draw.text((x1 + (x2 - x1 - (bbox[2] - bbox[0])) // 2, y), line, font=font, fill="#111827")
        y += 31


def arrow_head(draw: ImageDraw.ImageDraw, previous: tuple[int, int], end: tuple[int, int], color: str) -> None:
    px, py = previous
    ex, ey = end
    if abs(ex - px) >= abs(ey - py):
        direction = 1 if ex > px else -1
        pts = [(ex, ey), (ex - direction * 18, ey - 10), (ex - direction * 18, ey + 10)]
    else:
        direction = 1 if ey > py else -1
        pts = [(ex, ey), (ex - 10, ey - direction * 18), (ex + 10, ey - direction * 18)]
    draw.polygon(pts, fill=color)


def draw_arrow_path(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: str = "#374151") -> None:
    draw.line(points, fill=color, width=4, joint="curve")
    arrow_head(draw, points[-2], points[-1], color)


def main() -> None:
    img = Image.new("RGB", (1500, 760), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(FONT_HEI), 26)

    boxes = [
        ("React 前端\n文本/语音输入", (45, 305, 305, 425), "#E8F3FF"),
        ("FastAPI MessageService\n会话、路由、SSE", (390, 305, 700, 425), "#EEF8E8"),
        ("DeepSeek LLM\n回复与 emotion 标签", (800, 85, 1115, 190), "#FFF4DB"),
        ("Edge-TTS / ASR\n语音链路", (800, 310, 1115, 415), "#F4EAFE"),
        ("PostgreSQL / pgvector\n消息、记忆、会话", (800, 535, 1115, 640), "#FFECEC"),
        ("前端播放与表现\n文字、音频、Live2D", (1240, 305, 1480, 425), "#EAF5F5"),
    ]

    for text, xy, fill in boxes:
        draw_box(draw, xy, text, font, fill)

    # Main request path.
    draw_arrow_path(draw, [(305, 365), (390, 365)])

    # MessageService fans out to model, voice service, and database without crossing boxes.
    draw_arrow_path(draw, [(700, 325), (750, 325), (750, 138), (800, 138)])
    draw_arrow_path(draw, [(700, 365), (800, 365)])
    draw_arrow_path(draw, [(700, 405), (750, 405), (750, 588), (800, 588)])

    # Three service outputs converge at the display/playback box edge.
    draw_arrow_path(draw, [(1115, 138), (1175, 138), (1175, 330), (1240, 330)])
    draw_arrow_path(draw, [(1115, 365), (1240, 365)])
    draw_arrow_path(draw, [(1115, 588), (1175, 588), (1175, 400), (1240, 400)])

    out = OUT / "fig4-1-data-flow-no-title.png"
    img.save(out)
    print(out)


if __name__ == "__main__":
    main()
