# Phase 2 架构深化 —— 完成报告

**日期**: 2026-06-24  
**分支**: `codex/mvp`  
**提交**: `beab49af`  
**作者**: Marshall77  
**Co-Authored-By**: Claude Opus 4.7

---

## 一、变更摘要

按照 `ShinobuChat Phase 2 Architecture Deepening.docx` 要求，完成以下 7 大模块的实现，将项目从"功能型 MVP"升级为"可维护、可解释、可产品化的 Agent 平台"。

| # | 模块 | 说明 |
|---|------|------|
| 1 | **PromptTrace** | 每条消息写入上下文元数据快照 |
| 2 | **ActionAuditLog** | 统一审计模型，覆盖 6 种来源 |
| 3 | **ToolRegistry 接入** | policy denied + executed+verified 双路径审计 |
| 4 | **Browser/Download 接入** | BrowserFacadeService 全方法 ActionAudit |
| 5 | **MCP 接入** | server-level 拒绝写入审计 |
| 6 | **下载风险强化** | DownloadRiskDecision 形式化，硬封锁不可覆盖 |
| 7 | **Debug API + 前端** | 6 个授权端点 + ActionAuditPanel 组件 |

---

## 二、修改文件清单

### 新增文件 (10)

```
app/models/action_audit_log.py          -- 统一审计模型
app/models/prompt_trace.py              -- 上下文追踪模型
app/services/action_audit_service.py    -- 审计服务 (含脱敏函数)
app/services/prompt_trace_service.py    -- 追踪服务
app/schemas/action_audit.py             -- 审计响应 Schema
app/schemas/debug_trace.py              -- 追踪响应 Schema
app/api/v1/routes/debug.py              -- Debug API 路由
frontend/shinobu-chat/src/api/debug.ts  -- 前端 Debug API 客户端
frontend/shinobu-chat/src/debug/ActionAuditPanel.tsx  -- 审计面板组件
docs/architecture/phase2-explainability-security-after-f14-f16.md  -- 架构文档
```

### 修改文件 (8)

```
app/models/__init__.py                  -- 注册 ActionAuditLog, PromptTrace
app/db/init_db.py                       -- ensure_phase2_columns()
app/api/v1/api.py                       -- 注册 debug router
app/services/agents/coordinator.py      -- AgentPlan + trace_context
app/services/turn/conversation_turn_service.py  -- PromptTrace 写入
app/services/tool_registry.py           -- execute_verified 审计
app/services/browser/browser_facade_service.py  -- 全方法 ActionAudit
app/services/download_risk_classifier.py -- DownloadRiskDecision + 硬封锁
app/mcp/server.py                       -- MCP reject 审计
```

---

## 三、架构变化

### 3.1 消息链路变化

```
之前:
  消息 → 路由 → AI → 回复  (无追踪，不可解释)

之后:
  消息 → PromptTrace(上下文快照)
       → 路由 → AI → 回复
       ↘ Tool/Browser/MCP → ActionAuditLog(统一审计)
       → Debug API → 用户自查
```

### 3.2 数据流

```
ConversationTurnService.prepare_turn()
  ├── AgentCoordinator.prepare() → AgentPlan.trace_context
  └── PromptTraceService.create_trace()  ← 写入元数据快照

AgentOrchestrator.run() → ToolRegistry.execute_verified()
  ├── ToolPolicyService.check()       → 拒绝 → ActionAuditLog
  └── ToolVerifier.verify()           → 通过/失败 → ActionAuditLog

BrowserFacadeService.read/search/summarize/open-url
  ├── BrowserActionLogService.record()  (原有日志)
  └── ActionAuditService.record()       (新增统一审计)

DownloadService.classify()
  └── DownloadRiskClassifier._decide() → DownloadRiskDecision
       └── ActionAuditService.record() per candidate

MCP Server.handle_request()
  └── _audit_mcp_rejection()  ← blocked/disabled/no-user
```

### 3.3 三层安全

| 层级 | 机制 | 不可被覆盖 |
|------|------|-----------|
| Hard blocklist | `javascript:`, `127.0.0.1`, `.jpg.exe` | 是 |
| Trusted source | 用户配置的信任域 | Trusted source **不能**覆盖 hard block |
| LLM advisory | 仅信息参考 | 是 |

---

## 四、兼容性说明

| 约束 | 状态 |
|------|------|
| 不改变现有 API 路径 | 通过 |
| 不改变 SSE event 名称 | 通过 |
| 不破坏 `/api/v1/messages` 流式行为 | 通过 |
| 不破坏 Browser/LocalAgent/MCP/Tasks 路由 | 通过 |
| 新增 Debug API 不影响现有路由 | 通过 |
| AgentPlan 新增 trace_context (field default) | 向后兼容 |
| audit 写入失败不抛出异常 | 保证主路径不受影响 |
| 不保存 system prompt/tool schema/网页正文/API key | 通过 |

---

## 五、安全与隐私

### 保护措施

- `ActionAuditService.redact_payload()` 自动替换 `api_key`, `token`, `password`, `secret` 为 `***REDACTED***`
- `PromptTrace` 只保存 SHA 哈希，不保存原文
- Debug API 强制 `current_user_id` 隔离
- 审计结果摘要截断至 500 字符
- Browser audit 只保存 `content_length` / `link_count`，不保存网页正文

### 风险评估

- **无风险**: 不存在 system prompt 或 tool schema 泄露
- **无风险**: 不存在 API key 明文存储
- **低风险**: SHA 哈希可反向推测内容变化，但不可还原原文

---

## 六、测试结果

| 命令 | 结果 |
|------|------|
| `python -m pytest tests/ -q` | **551 passed**, 1 pre-existing failure |
| `npm run build` | **passed** (built in 2.43s) |
| `npm run typecheck` | **passed** (0 errors) |
| `npm test` | **15 passed** (5 test files) |

唯一失败 (`test_diaries.py::test_llm_non_json_falls_back`) 为预存问题，与本次变更无关。

---

## 七、Debug API 端点

```
GET  /api/v1/debug/prompt-traces/conversations/{id}   -- 会话的追踪列表
GET  /api/v1/debug/prompt-traces/messages/{id}         -- 单条消息的追踪
GET  /api/v1/debug/action-audits                       -- 审计列表 (按 source 过滤)
GET  /api/v1/debug/action-audits/{id}                  -- 单条审计
GET  /api/v1/debug/action-audits/conversations/{id}    -- 会话的审计列表
GET  /api/v1/debug/action-audits/messages/{id}         -- 消息的审计列表
```

所有端点要求 Bearer Token 认证，用户只能查看自己的数据。

---

## 八、已知限制

| 项目 | 说明 | 计划 |
|------|------|------|
| `memory_ids` | MemoryAgent 当前只返回文本不返回 ID | Phase 3 实现 `search_hits()` |
| `pinned_prefix_sha` | PrefixCacheManager 未接入 Pipeline | Phase 3 接入 PromptTrace |
| `tool_names_available` | AgentCoordinator 未渲染工具目录 | Phase 3 接入 |
| 前端 TracePanel | 尚未实现 PromptTrace 前端查看器 | Phase 3 |

---

## 九、未完成事项 / 下一阶段建议

1. **MemoryAgent.search_hits()** — 返回 memory ID 列表，使 prompt trace 的 memory_ids 有意义
2. **PrefixCacheManager Pipeline 接入** — 将 SHA 值写入 PromptTrace
3. **TracePanel 前端组件** — 类似 ActionAuditPanel 的 PromptTrace 查看器
4. **SettingsPage 集成** — 将 ActionAuditPanel 接入设置页面
5. **Prometheus Metrics** — 为生产环境添加指标端点
6. **Phase 3** — 可考虑：音视频通话、多设备同步、Agent 安全沙箱
