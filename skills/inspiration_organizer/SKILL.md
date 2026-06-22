---
name: inspiration-organizer
description: 按标签整理灵感类记忆，归类、去重并提出可落地的下一步行动
keywords: [灵感, 点子, 创意, 分类, 标签, inspiration]
version: 1.0.0
---

# Inspiration Organizer

## Trigger

当用户说"整理灵感""归类点子""帮我理一下创意""organize ideas"或需要梳理零散想法时使用这个 Skill。

## Workflow

1. 调用 `conversation_digest`，设置 `limit=50`。
2. 筛选灵感类内容：设计想法、产品概念、写作片段、实验思路等。
3. 对相似想法去重。
4. 为每个条目分配 1-3 个标签，优先使用具体标签如 `product`、`ui`、`story`、`agent`、`memory`、`research`。
5. 为最强的想法建议一个小的下一步行动。

## Output

输出格式：

## 标签索引
- 标签: 想法标题

## 灵感条目
- 标题: 简述
  标签: 标签1, 标签2
  下一步: 具体行动
