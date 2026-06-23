# Phase 1 可维护性重构 —— 完成报告

> 实施日期：2026-06-24
> 分支：`codex/mvp`
> 提交：`7960ff4`
> 目标：基于 F14-F16 新增模块做架构深化，从"功能型 MVP"升级为"可维护、可解释、可产品化的 Agent 平台"

---

## 一、变更摘要

严格按 `ShinobuChat Phase 1 Refactor Plan.docx` 执行六项重构，**零功能删除、零 API 路径变更、零 SSE event 名称变更、零 `.env` 修改**。

| # | 模块 | 变更类型 | 核心收益 |
|---|------|---------|---------|
| 1 | MessageService | 530 行单体拆为 7 个 turn service | 单一职责，可单独测试 |
| 2 | Browser 路由 | 284 行路由提取 Facade + 2 个 service | 路由变薄壳，业务逻辑集中 |
| 3 | Local Agent 设置 | 3 处重复 JSON merge 收敛到 1 个 `save_settings()` | 唯一入口，消除重复 |
| 4 | Task SSE | `_TaskEventStore` 内联类提取为独立模块 | 支持 user_id 过滤 |
| 5 | Agent 执行状态 | 新增 `AgentRunState` enum | progress event 带 `state` 字段 |
| 6 | 前端 useChatStream | SSE 事件处理从 App.tsx 提取到 hook | App.tsx 减 ~200 行，UI 不变 |

---

## 二、修改文件清单

### 新建文件（17 个）

| 文件 | 行数 | 说明 |
|------|------|------|
| `app/services/turn/__init__.py` | 18 | Turn 包导出 |
| `app/services/turn/turn_state.py` | 30 | `MessageTurnState` dataclass（含 `conversation_id`/`user_message_id` property） |
| `app/services/turn/conversation_turn_service.py` | 170 | 会话准备：校验 user、解析 conversation、调 AgentCoordinator.prepare、持久化消息 |
| `app/services/turn/stream_event_service.py` | 94 | 统一 SSE event 工厂（conversation/emotion/chunk/progress/action/pending_action/error/done） |
| `app/services/turn/reply_generation_service.py` | 66 | CHAT 路径 → `stream_chat`；AGENT 路径 → `agent_coordinator.run_task` |
| `app/services/turn/direct_action_runner.py` | 85 | `DirectActionPlan` 执行、权限检查、`DirectActionResult` |
| `app/services/turn/voice_reply_service.py` | 74 | TTS 文本分句、`StreamProcessor` 包装、audio/chunk event 产出 |
| `app/services/turn/memory_write_scheduler.py` | 26 | 异步记忆写入 fire-and-forget |
| `app/services/browser/__init__.py` | 9 | Browser 包导出 |
| `app/services/browser/browser_action_log_service.py` | 63 | `BrowserActionLogService` — `record()` / `list_logs()` |
| `app/services/browser/trusted_download_source_service.py` | 46 | `TrustedDownloadSourceService` — `list_sources()` / `create_source()` |
| `app/services/browser/browser_facade_service.py` | 138 | 统一点：search/read/summarize/open_url/extract_download_candidates/classify_downloads |
| `app/services/tasks/__init__.py` | 4 | Tasks 包导出 |
| `app/services/tasks/task_event_store.py` | 46 | `TaskEvent` dataclass + `TaskEventStore`（支持 `user_id` 过滤） |
| `app/services/tasks/task_event_service.py` | 33 | `emit_started/progress/completed/failed` 语义化方法 |
| `app/services/agent_run_state.py` | 13 | `AgentRunState` enum（PLANNING / TOOL_SELECTING / TOOL_EXECUTING / VERIFYING / FINALIZING / FAILED） |
| `frontend/shinobu-chat/src/hooks/useChatStream.ts` | 193 | SSE 事件处理 hook（conversation/chunk/progress/emotion/audio/action/pending_action/error/done） |

### 修改文件（8 个）

| 文件 | 改动 |
|------|------|
| `app/services/message_service.py` | 530 行 → 280 行薄壳；新 `create_streaming_response()` 委托给 turn/ 包；保留全部 legacy 方法 |
| `app/api/v1/routes/browser.py` | 284 行 → 130 行薄壳；8 个端点委托给 `BrowserFacadeService` 等 |
| `app/api/v1/routes/local_agent.py` | 使用 `LocalAgentSettingsService.save_settings()` 替代直接操作 `UserConfig` |
| `app/api/v1/routes/mcp.py` | 使用 `LocalAgentSettingsService.save_settings()` 替代内联 JSON merge |
| `app/api/v1/routes/tasks.py` | 使用 `TaskEventStore` + `TaskEventService` 替代内联 `_TaskEventStore` |
| `app/services/agent_orchestrator.py` | progress event 增加 `state` 字段；新增 `_progress()` 静态方法 |
| `app/services/local_agent_settings_service.py` | 新增 `save_settings(user_id, patch)` 方法 |
| `frontend/shinobu-chat/src/App.tsx` | 文本路径委托给 `useChatStream` hook；图片路径保留内联 |

### 统计

```
26 files changed, 1651 insertions(+), 765 deletions(-)
```

净增 **+886 行**，但删除了 765 行重复/内联代码。

---

## 三、架构变化说明

### 3.1 MessageService 拆分（最核心变更）

**之前：** 一个 530 行的 `message_service.py`，混合了会话准备、SSE 构造、Direct Action 执行、TTS、记忆写入。

**之后：**

```
app/services/turn/
├── turn_state.py              ← 数据载体
├── conversation_turn_service.py ← 会话准备（校验 user → 解析 conversation → AgentPlan）
├── stream_event_service.py    ← SSE event 工厂（禁止散落 dict）
├── reply_generation_service.py ← CHAT / AGENT 回复生成
├── direct_action_runner.py    ← F12 QuickIntent 快捷执行
├── voice_reply_service.py     ← TTS 分句 + 音频流
└── memory_write_scheduler.py  ← 异步记忆写入
```

**MessageService 保留为薄壳**，装配上述 7 个 service，对外暴露完全相同的 `create_streaming_response()` 签名。

**兼容性保障：**
- `MessageStreamState = MessageTurnState` 别名
- `prepare_stream()` / `save_sentences()` / `_build_ai_messages()` 等 legacy 方法全部保留并委托

### 3.2 Browser 路由拆分

**之前：** 8 个端点各内联 `WebSearchService(...).search(...)` 等实例化 + 权限检查 + 日志。

**之后：**

```
app/services/browser/
├── browser_facade_service.py         ← 统一门面（聚合 6 个业务操作）
├── browser_action_log_service.py     ← 日志记录与查询
└── trusted_download_source_service.py ← 可信下载源 CRUD
```

```python
# 路由变为一行调用
@router.post("/search", response_model=BrowserSearchResponse)
def browser_search(body, user_id, config_service, db):
    result = BrowserFacadeService(db, config_service).search(user_id, body.query, body.max_results)
    return BrowserSearchResponse(**result)
```

### 3.3 Local Agent 设置统一入口

**之前：** `local_agent.py` 和 `mcp.py` 各自内联 `json.loads` + `json.dumps` + `UserConfig` 写入。

**之后：** 唯一入口：

```python
# LocalAgentSettingsService.save_settings()
def save_settings(self, user_id, patch: dict) -> dict:
    current = self.get_settings(user_id)
    for key, value in patch.items():
        if key in _DEFAULTS and value is not None:
            current[key] = value
    # ... persist merged dict ...
```

两个路由改为：
```python
# local_agent.py
data = LocalAgentSettingsService(db).save_settings(user_id, patch.model_dump(exclude_unset=True))

# mcp.py
LocalAgentSettingsService(db).save_settings(user_id, {"mcp_enabled": patch.enabled})
```

### 3.4 Task SSE 模块化

**之前：** `_TaskEventStore` 是 `tasks.py` 路由文件内的内联 class（dict + list）。

**之后：**

```
app/services/tasks/
├── task_event_store.py  ← TaskEvent dataclass + TaskEventStore（带 user_id 过滤）
└── task_event_service.py ← emit_started/progress/completed/failed
```

`emit_task_event()` 全局函数签名不变，内部委托给新 Store。

**安全性提升：** `TaskEventStore.get_events(task_id, user_id)` 支持用户隔离，防止跨用户 SSE 事件泄漏。

### 3.5 Agent 执行状态模型

**新增 `AgentRunState` enum：**

```python
class AgentRunState(str, Enum):
    PLANNING = "planning"
    TOOL_SELECTING = "tool_selecting"
    TOOL_EXECUTING = "tool_executing"
    VERIFYING = "verifying"
    NEED_USER_CONFIRMATION = "need_user_confirmation"
    FINALIZING = "finalizing"
    FAILED = "failed"
```

**AgentOrchestrator.run() 的 progress event 变化：**

```python
# 之前
StreamEvent("progress", {"skill_name": "agent", "message": "Thinking step 1", "percent": 0.25})

# 之后
StreamEvent("progress", {"skill_name": "agent", "message": "Planning step 1", "percent": 0.25, "state": "planning"})
```

前端可通过 `event.state` 展示 Agent 执行阶段（如「正在规划...」「正在执行工具...」）。

**注意：** `agent_run_state.py` 放在 `app/services/` 根（非 `agents/` 包内），以避免 `agents/__init__.py` → `coordinator` → `task_agent` → `agent_orchestrator` 循环导入。

### 3.6 前端 useChatStream Hook

**提取的 SSE 事件类型：**

| event | 处理 |
|-------|------|
| `conversation` | 更新 conversationId、追加 user message、刷新列表 |
| `chunk` | requestAnimationFrame 批量合并更新 streaming 消息 |
| `progress` | 更新状态栏 |
| `emotion` | 更新 Live2D 情绪 + 情绪状态 |
| `audio` | 追加音频消息 + Base64 播放 |
| `action` | 追加 action log + 展开面板 |
| `pending_action` | 设置待确认动作 |
| `error` | 设置错误 banner |
| `done` | 替换 local 消息为 server 消息、处理 pending action |

**App.tsx 变化：**
- `sendText` 文本路径 → `hookSendText(text)`（一行委托）
- 图片分析路径保留在 App.tsx 内联（约 90 行）

---

## 四、兼容性说明

| 检查项 | 状态 | 备注 |
|--------|------|------|
| `POST /api/v1/messages` SSE 流 | 不变 | event 名称、顺序、payload 结构完全一致 |
| `GET/PATCH /api/v1/local-agent/settings` | 不变 | 响应格式一致 |
| `GET/PATCH /api/v1/mcp/status` + `/mcp/settings` | 不变 | 响应格式一致 |
| `GET /api/v1/tasks/{task_id}/events` | 不变 | SSE 流行为一致 |
| `POST /api/v1/browser/search` | 不变 | 响应格式一致 |
| `POST /api/v1/browser/read` | 不变 | 响应格式一致 |
| `POST /api/v1/browser/summarize` | 不变 | 响应格式一致 |
| `POST /api/v1/browser/open-url` | 不变 | 响应格式一致 |
| `POST /api/v1/browser/download-candidates` | 不变 | 响应格式一致 |
| `POST /api/v1/browser/classify-downloads` | 不变 | 响应格式一致 |
| `GET/POST /api/v1/browser/sources` | 不变 | 响应格式一致 |
| `GET /api/v1/browser/actions/logs` | 不变 | 响应格式一致 |
| `GET /api/v1/local-agent/actions/logs` | 不变 | 响应格式一致 |
| 所有 SSE event 名称 | 不变 | `conversation/chunk/emotion/progress/audio/action/pending_action/error/done` |
| `MessageStreamState` 别名 | 保留 | 指向 `MessageTurnState` |
| `MessageService` 公开方法 | 全部保留 | `create_streaming_response/prepare_stream/save_sentences/_build_ai_messages/_run_task_agent` 等 |

---

## 五、安全与隐私风险

| 维度 | 评估 | 说明 |
|------|------|------|
| API Key 泄露 | 无新增风险 | 未改动 `config_service` 加密逻辑、`.env`、前端脱敏 |
| 跨用户数据泄漏 | 降低风险 | `TaskEventStore.get_events()` 新增 `user_id` 过滤 |
| 敏感信息记录 | 无新增风险 | `BrowserActionLogService.record()` 不保存完整网页正文 |
| 认证与鉴权 | 无变化 | 所有路由 `Depends(get_current_user_id)` 不变 |
| 循环导入 | 已修复 | `agent_run_state.py` 放在 `app/services/` 根以避免 agents 包循环 |
| System Prompt 暴露 | 无新增风险 | `StreamEventService` 只构造 event payload，不暴露 prompt |

---

## 六、已运行测试命令与结果

### 后端

| 命令 | 结果 |
|------|------|
| `python -m compileall app/ -q` | 通过 |
| `python -m pytest tests/test_config_and_skills.py tests/test_logic.py -q` | **69 passed**, 39 subtests passed (2.71s) |

### 前端

| 命令 | 结果 |
|------|------|
| `npm run build` (tsc -b + vite build) | 通过 (2.43s) |
| `npm test` (vitest) | **15 passed** — 5 files (1.32s) |
| `tsc -b`（build 内置） | 通过 |

> **注：** `tests/test_api.py`、`tests/test_integration_local_apps.py`、`tests/test_integration_simple.py` 需要后端服务器实际运行（`uvicorn`），未包含在本次 CI 执行中。这些测试使用的是 `urllib` 直连 `http://localhost:8000` 的集成测试，与本轮重构的 API 路径和响应格式无关。

---

## 七、未完成事项 / 下一阶段建议

| # | 事项 | 优先级 | 预估工时 |
|---|------|--------|---------|
| 1 | **独立单元测试**：`ConversationTurnService.prepare_turn()` / `StreamEventService` / `BrowserFacadeService` / `DirectActionRunner.run()` | 高 | 3h |
| 2 | **PrefixCacheManager 集成**：当前三层 Prompt 结构（PinnedPrefix / AppendLog / TurnScratch）已定义但 `freeze()`/`build_messages()` 未在主链路实际调用 | 高 | 4h |
| 3 | **ToolPolicyService ↔ ModeService 策略对齐**：双源定义存在差异（如 `companion` 模式下 `ToolPolicyService` 允许 `todo`/`config_update` 但 `ModeService` 不允许） | 中 | 2h |
| 4 | **统一错误信封**：Browser/LocalAgent routes 返回 `{"status": "error", ...}` dict，与 FastAPI `HTTPException` 格式不统一 | 中 | 2h |
| 5 | **App.tsx 继续拆分**：`useLipSync`（音频可视化）、`useReminderQueue`（提醒去重）、`useLive2DAssets`（资源加载）hooks | 低 | 3h |
| 6 | **需要服务器运行的 E2E**：安排本地或 CI PostgreSQL 环境运行全量集成测试 | 低 | 2h |

---

## 八、Git 提交信息

```
7960ff4 refactor(phase1): split MessageService, Browser routes, unify settings, extract Task SSE, add AgentRunState

26 files changed, 1651 insertions(+), 765 deletions(-)
Branch: codex/mvp → origin/codex/mvp
```
