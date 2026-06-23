# Phase 1 可维护性重构（F14-F16 之后）

> 实施日期：2026-06-24
> 分支：codex/mvp
> 目标：不增加新功能，将 F14-F16 新增模块的工程结构整理为可维护、可解释的 Agent 平台基线

## 一、重构模块总览

| # | 模块 | 变更类型 | 说明 |
|---|------|---------|------|
| 1 | MessageService | 拆分 | 530 行单体拆为 7 个 turn service |
| 2 | Browser 路由 | 拆分 | 8 个端点直写逻辑提取为 Facade + Log + TrustedSource 三个 service |
| 3 | Local Agent 设置 | 统一 | 所有 UserConfig 读写收敛到 LocalAgentSettingsService.save_settings() |
| 4 | Task SSE | 整理 | _TaskEventStore 提取为独立模块，支持 user_id 过滤 |
| 5 | Agent 执行状态 | 新增 | AgentRunState enum，progress event 增加 state 字段 |
| 6 | 前端 useChatStream | 拆分 | SSE 事件处理逻辑从 App.tsx 提取到 hook |

## 二、MessageService 拆分

### 之前

`app/services/message_service.py` 530 行，混合了：
- 会话准备（用户校验、conversation 创建、AgentPlan 组装）
- SSE event 构造（散落 dict）
- Direct action 执行（内联 LocalAppService）
- TTS 分句 + 流式音频
- 异步记忆写入
- run_task_agent 旧路径

### 之后

`app/services/turn/` 包 7 个文件：

| 文件 | 职责 | 行数 |
|------|------|------|
| `turn_state.py` | `MessageTurnState` dataclass | ~30 |
| `conversation_turn_service.py` | 会话准备、用户校验、AgentPlan 组装、消息持久化 | ~130 |
| `stream_event_service.py` | 统一 SSE event 工厂（conversation/emotion/chunk/progress/action/pending_action/error/done） | ~90 |
| `reply_generation_service.py` | CHAT 路径 → stream_chat；AGENT 路径 → agent_coordinator.run_task | ~60 |
| `direct_action_runner.py` | DirectActionPlan 执行、权限检查、pending_action 构造 | ~75 |
| `voice_reply_service.py` | TTS 分句、StreamProcessor、audio/chunk event 产出 | ~55 |
| `memory_write_scheduler.py` | 异步记忆写入 fire-and-forget | ~20 |

`MessageService` 保留为薄壳（~280 行），负责装配和协调，保留所有 legacy 方法签名（`prepare_stream`、`save_sentences`、`_build_ai_messages` 等）。

### 兼容性

- `MessageStreamState = MessageTurnState` 别名保留
- `create_streaming_response()` 签名和 SSE event 不变
- 所有 legacy 方法委托到新 service

## 三、Browser 路由拆分

### 之前

`app/api/v1/routes/browser.py` 284 行，每个端点内联：
- WebSearchService/WebReaderService 实例化
- LocalAgentSettingsService 权限检查
- _log_browser_action() helper
- TrustedDownloadSource 直接查询

### 之后

`app/services/browser/` 包 3 个文件：

| 文件 | 职责 |
|------|------|
| `browser_action_log_service.py` | `BrowserActionLogService` — record() / list_logs() |
| `trusted_download_source_service.py` | `TrustedDownloadSourceService` — list_sources() / create_source() |
| `browser_facade_service.py` | `BrowserFacadeService` — search/read/summarize/open_url/extract_download_candidates/classify_downloads 统一入口，聚合权限检查 + 日志 + 业务逻辑 |

`browser.py` 路由变为薄壳（~130 行）：仅负责 Depends 注入、调 facade、返回 response model。

### 兼容性

- 所有路由路径不变
- 所有 response model 不变
- 权限检查和日志记录行为不变

## 四、Local Agent 设置统一

### 变更

- `LocalAgentSettingsService` 新增 `save_settings(user_id, patch)` 方法 —— 合并 patch 到当前设置并持久化
- `local_agent.py` GET/PATCH `/settings` 改为调用 service 而非直接操作 `UserConfig`
- `mcp.py` PATCH `/settings` 改为调用 `LocalAgentSettingsService.save_settings()` 而非内联 JSON merge

### 收益

- 消除 3 处重复的 JSON merge + UserConfig 写入逻辑
- 设置读写唯一入口，未来加字段只需改 `_DEFAULTS`

## 五、Task SSE 事件系统

### 之前

`app/api/v1/routes/tasks.py` 内联 `_TaskEventStore` class（dict-based 简单队列）。

### 之后

`app/services/tasks/` 包 2 个文件：

| 文件 | 职责 |
|------|------|
| `task_event_store.py` | `TaskEvent` dataclass + `TaskEventStore`（支持 user_id 过滤） |
| `task_event_service.py` | `TaskEventService`（emit_started/progress/completed/failed 语义化方法） |

`emit_task_event()` 全局函数签名不变，内部委托给新 Store。

## 六、Agent 执行状态模型

### 新增

`app/services/agent_run_state.py`：

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

`AgentOrchestrator.run()` 的 progress event 增加 `state` 字段（如 `"state": "tool_executing"`），前端可据此展示 Agent 执行阶段。

### 注意

`run_state.py` 放在 `app/services/agent_run_state.py`（而非 `agents/` 包内），以避免循环导入（agents 包初始化链 → coordinator → task_agent → agent_orchestrator）。

## 七、前端 useChatStream Hook

### 新增

`frontend/shinobu-chat/src/hooks/useChatStream.ts`

提取 SSE 事件处理逻辑（conversation/chunk/progress/emotion/audio/action/pending_action/error/done）从 App.tsx，通过 `UseChatStreamDeps` 接口注入所有状态操作回调。

`App.tsx` 的 `sendText` 函数：
- 文本路径委托给 `hookSendText(text)`
- 图片路径保留在 App.tsx 内联

### 兼容性

- UI 行为完全不变
- 图片分析、语音输入、Live2D 不受影响

## 八、兼容性说明

| 检查项 | 状态 |
|--------|------|
| `/api/v1/messages` SSE 流 | 不变 |
| `/api/v1/browser/*` 路由 | 不变 |
| `/api/v1/local-agent/settings` | 不变 |
| `/api/v1/mcp/status` + `/mcp/settings` | 不变 |
| `/api/v1/tasks/{task_id}/events` | 不变 |
| SSE event 名称 | 全部不变 |
| 旧 import 路径 | `MessageStreamState` 别名保留 |

## 九、安全与隐私

- 不改动 API Key 加密逻辑
- 不改动 `.env` 或密钥存储
- 新增 action log 记录不保存完整网页正文或 system prompt
- `emit_task_event()` 新增 `user_id` 过滤，防止跨用户事件泄漏

## 十、验证结果

### 后端

```
python -m pytest tests/test_config_and_skills.py tests/test_logic.py -q
69 passed, 39 subtests passed
```

### 前端

```
npm run build  — 通过
npm test       — 15 passed (5 test files)
tsc -b         — 通过（build 内置）
```

### 编译检查

```
python -m compileall app/ -q  — 通过
```

## 十一、未完成 / 下一阶段建议

1. **单元测试补充**：`ConversationTurnService`、`StreamEventService`、`BrowserFacadeService` 的独立单元测试
2. **PrefixCacheManager 集成**：当前三层 Prompt 结构已定义但未在主链路实际使用 `freeze()/build_messages()`
3. **ToolPolicyService 与 ModeService 对齐**：双源策略定义存在差异（如 companion 模式）
4. **App.tsx 继续拆分**：`useLipSync`、`useReminderQueue`、`useLive2DAssets` hooks
5. **需要服务器运行的 E2E 测试**：`test_api.py`、`test_integration_*.py` 需要后端实际运行
