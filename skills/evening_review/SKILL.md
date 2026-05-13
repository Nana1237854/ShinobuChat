---
name: evening_review
description: 晚间复盘今日消息与记忆，提炼进展、情绪、待跟进事项和明日建议。
metadata: {"echo":{"emoji":"review"}}
---

# Evening Review

Use this skill when the user asks for 晚间复盘, 今日总结, review today, or wants to reflect on today's messages and memory.

## Workflow

1. Call `conversation_digest` with enough recent messages, usually `limit=40`.
2. Extract:
   - 今日做过或讨论过的事
   - 用户的情绪和能量变化
   - 明确承诺、待办、风险
   - 值得保存的长期记忆候选
3. If the digest is too thin, say so directly and summarize only available context.

## Output

Use four short sections:

1. 今日脉络
2. 关键收获
3. 待跟进
4. 明日建议
