---
name: screen_reader
description: 截屏 + OCR，把用户提供的屏幕截图转换成可读文本并总结界面重点。
metadata: {"echo":{"emoji":"screen"}}
---

# Screen Reader

Use this skill when the user asks to read the screen, OCR a screenshot, understand an image, or says 截屏/截图/读屏.

## Workflow

1. Check whether an image or screenshot content is available in the current request.
2. If no image is available, ask the user to attach a screenshot or use the frontend screenshot action, then send the image back into chat.
3. If image input is available through the active model, ask the model to extract visible text, UI state, errors, and actionable controls.
4. If OCR tooling is available in the runtime, use it; otherwise use model vision.

## Output

Return:

- Visible text
- What the screen appears to be
- Important warnings or errors
- Suggested next action

Do not invent text that is not visible.
