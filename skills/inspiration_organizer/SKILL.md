---
name: inspiration_organizer
description: 按标签整理 inspiration 类型记忆，把零散灵感归类、去重并提出可落地下一步。
metadata: {"echo":{"emoji":"inspiration"}}
---

# Inspiration Organizer

Use this skill when the user asks to organize inspirations, 灵感, 点子, ideas, creative notes, or tagged memories.

## Workflow

1. Call `conversation_digest` with `limit=50`.
2. Select inspiration-like content: ideas, design sparks, product concepts, writing fragments, experiments.
3. Deduplicate similar ideas.
4. Assign 1-3 tags per item. Prefer concrete tags, for example `product`, `ui`, `story`, `agent`, `memory`, `research`.
5. Suggest one small next action for the strongest ideas.

## Output

Use this shape:

## 标签索引
- tag: idea titles

## 灵感条目
- Title: summary
  Tags: tag, tag
  Next: small action
