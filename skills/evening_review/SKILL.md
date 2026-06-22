---
name: evening-review
description: 晚间复盘当日的对话与记忆，提炼进展、情绪变化、待跟进事项和明日建议
keywords: [复盘, 总结, 晚间, 回顾, 今日, review]
version: 1.0.0
---

# Evening Review

## Trigger

当用户说"晚间复盘""帮我总结今天""回顾一下今天""review today"时使用这个 Skill。

## Workflow

1. 调用 `conversation_digest`，设置 `limit=40` 获取足够的当日消息。
2. 提取以下内容：
   - 今日讨论或完成的事项
   - 用户的情绪与能量变化
   - 明确的承诺、待办、风险点
   - 值得保存为长期记忆的候选内容
3. 如果上下文信息太少，如实说明，仅总结可用内容。

## Output

输出四个小节：

1. 今日脉络
2. 关键收获
3. 待跟进
4. 明日建议
