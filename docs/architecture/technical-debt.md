# ShinobuChat 技术债记录

> 最后更新: 2026-06-24
> 分支: codex/mvp

---

## 1. FastAPI on_event → lifespan 迁移

**严重度:** 低 | **波及范围:** `app/main.py`

**现状:**
- 当前 `main.py` 仍使用 `@app.on_event("startup")` 和 `@app.on_event("shutdown")`。
- FastAPI 新版本建议迁移到 `lifespan` async context manager。
- 当前测试出现 3 个 deprecation warnings：
  ```
  DeprecationWarning: on_event is deprecated, use lifespan event handlers instead.
  ```

**风险:**
- 短期不影响运行，FastAPI 0.x 仍支持 `on_event`。
- 长期 FastAPI 1.x 升级时可能需要迁移。

**后续迁移建议:**
1. 使用 `asynccontextmanager` 定义 lifespan：
   ```python
   from contextlib import asynccontextmanager

   @asynccontextmanager
   async def lifespan(app: FastAPI):
       # startup
       ConfigService.validate_encryption_key()
       _check_production_config()
       init_db()
       scheduler = create_default_scheduler()
       app.state.job_scheduler = scheduler
       scheduler.start()
       yield
       # shutdown
       scheduler = app.state.job_scheduler
       if scheduler:
           await scheduler.stop()

   app = FastAPI(lifespan=lifespan)
   ```
2. 迁移后补充 app startup/shutdown 集成测试。
3. 确认 JobScheduler 在 lifespan 模式下正确启停。

**优先级:** 中低。等 Phase 3 收口测试完全稳定后再做。

---

## 2. Browser open-url 权限模型

**严重度**: 低 | **波及范围**: `BrowserFacadeService`, `CapabilityRegistry`

**现状:**
- `open_url()` 使用 `browser_reader_enabled` 作为权限门禁。
- 当前实现是“打开系统默认浏览器跳转”，不是 Playwright 自动控制。
- 如果未来支持 Playwright 级别的浏览器自动化，需要将 `open_url` 移到 `browser_automation` 或新增 `browser_open` capability。

**架构决策 (2026-06-24):**
- 选方案 A: `browser_reader_enabled` 控制所有浏览器轻量能力（search / read / summarize / open-url）。
- `browser_automation_enabled` 仅控制未来更高风险的自动控制行为。
- 当前 open-url 是"打开默认浏览器跳转"，不是 Playwright 自动操作。

**后续考虑:**
- 如果 open-url 行为从"打开系统浏览器"升级为"Playwright 自动化"，应创建独立的 `browser_open` capability。

---

## 3. TaskEvent 持久化

**严重度**: 低 | **波及范围**: `TaskEventStore`, `TaskRunService`

**现状:**
- `TaskEventStore` 是纯内存存储，SSE 事件不持久化。
- `TaskRun` 模型已持久化任务元数据到 `task_runs` 表。
- 单进程部署足够；多进程需引入 Redis/PostgreSQL LISTEN 机制。

**后续考虑:**
- 多进程部署时，将 TaskEvent 广播从内存迁移到 PostgreSQL NOTIFY 或 Redis pub/sub。

---

## 4. MCP 多用户会话路由

**严重度**: 低 | **波及范围**: `app/mcp/server.py`

**现状:**
- MCP Server 通过 `SC_MCP_DEFAULT_USER_ID` 配置单一默认用户。
- 外部 Agent 调用的所有工具都以此用户身份执行。
- 不支持多用户会话隔离。

**后续考虑:**
- 如果 MCP 需要支持多用户，需要实现 OAuth / API key 级别的用户身份传递。
- 当前 MCP 默认关闭，单一用户模式风险可控。

---

## 5. Browser Automation sandbox

**严重度**: 低 | **波及范围**: `BrowserAutomationService`

**现状:**
- `BrowserAutomationService` 仅实现 `open_url()` 和 `snapshot()` 骨架。
- `snapshot()` 返回 "not_implemented"。
- 无 sandbox / 隔离机制。

**后续考虑:**
- 实现 Playwright 集成时需要 sandbox（容器或 seccomp）。
- 当前 `browser_automation_enabled` 默认关闭，风险可控。

---

## 6. Skill 确定性回放

**严重度**: 低 | **波及范围**: `SkillManager`, `SkillRunLogService`

**现状:**
- Skill 执行依赖 LLM 非确定性行为，无法保证同样输入产生同样输出。
- `SkillRunLog` 记录了 input_summary 和 output_summary，但不存储完整内容。

**后续考虑:**
- 如果需要确定性回放，需要记录完整的 LLM 请求/响应（当前审计策略不允许）。
- 可在开发模式（SC_DEBUG=true）下选择性启用完整记录。

---

## 7. Behavior A/B 测试框架

**严重度**: 低 | **波及范围**: `BehaviorEngine`

**现状:**
- `BehaviorEngine.decide()` 返回确定的 `BehaviorDecision`。
- 无 A/B 测试支持（无法对比不同 behavior 配置的效果）。

**后续考虑:**
- 需要实验框架支持用户分组和指标采集。
- 非 MVP 范围。
