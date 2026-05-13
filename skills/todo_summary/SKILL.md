---
name: todo_summary
description: 汇总用户 Todo，从近期对话中抽取待办事项、状态、优先级和下一步。
metadata: {"echo":{"emoji":"todo"}}
---

# Todo Summary

Use this skill when the user asks to summarize TODOs, 待办, 任务清单, next actions, or "我还有什么要做".

## Workflow

1. Call `conversation_digest` with `limit=50`.
2. Extract actionable items only. Do not turn vague wishes into tasks unless phrased as an intention.
3. Group by:
   - Today / soon
   - Later
   - Waiting for someone or something
4. Mark uncertain items with "可能".

## Output

Return a concise checklist in Chinese:

- [ ] Task - context / next step

If there are no clear TODOs, say no explicit TODO was found and mention the closest candidates.
