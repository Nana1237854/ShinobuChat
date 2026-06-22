---
name: shinobuchat-frontend-review
description: 审查 ShinobuChat 前端页面、API client、状态管理、设置面板和 Live2D 交互问题
keywords: [ShinobuChat, 前端, React, Vite, UI, Live2D, API, 设置面板]
version: 1.0.0
---

# ShinobuChat Frontend Review

## Trigger

当用户提交 ShinobuChat 前端变更、页面截图、控制台报错或 QA 报告后，需要检查前端逻辑和 UI 问题时使用这个 Skill。

适用场景包括：
- 设置页或面板乱码
- API client 字段不匹配
- token 未携带导致 401
- Live2D 显示异常
- SSE 流式输出异常
- Persona、Goal、Memory、Skill、Emotion 页面功能不完整
- CSS 视觉细节需要优化

## Workflow

1. 先确认前端路径和当前分支。
2. 检查 API client 是否复用统一 auth token。
3. 检查页面 loading、empty、error、saving 状态。
4. 检查是否直接展示后端 enum。
5. 检查中文文案是否乱码或过硬。
6. 检查 Live2D 和 SSE 是否有 fallback。
7. 检查样式是否有溢出、遮挡、滚动异常。
8. 修改后运行 npm run build。

## Output

输出应包含：
- 问题定位
- 影响范围
- 涉及文件
- 修复建议
- 验证步骤
- 构建结果
