---
name: shinobuchat-backend-review
description: 审查 ShinobuChat 后端提交中的接口、数据库、服务层、鉴权和测试风险
keywords: [ShinobuChat, 后端, FastAPI, SQLAlchemy, PostgreSQL, 测试, 代码审查]
version: 1.0.0
---

# ShinobuChat Backend Review

## Trigger

当用户提交 ShinobuChat 后端 commit、报错日志、接口变更或数据库变更后，需要检查后端逻辑和潜在风险时使用这个 Skill。

适用场景包括：
- FastAPI 路由新增或修改
- SQLAlchemy 模型字段变更
- PostgreSQL 表结构不一致
- pytest 失败
- 401、404、409、500 错误排查
- Memory、Goal、Reminder、Persona、Emotion、Skill 模块更新后复查

## Workflow

1. 先确认分支、commit 和变更范围。
2. 检查路由是否使用当前登录用户，不允许信任前端传入 user_id。
3. 检查模型字段和数据库初始化是否一致。
4. 检查旧库是否需要迁移或补列。
5. 检查 service 层是否吞异常、误报 404、或把业务冲突当 NotFound。
6. 检查 response_model 是否与实际 payload 匹配。
7. 检查测试是否覆盖 API 层、service 层和异常路径。
8. 输出阻断问题、中风险问题和可选优化。

## Output

输出应包含：
- 结论：可用 / 需修 / 阻断
- 高优先级问题
- 中低风险问题
- 推荐修复方式
- 需要补的测试
- 给后端 Agent 的修复提示词
