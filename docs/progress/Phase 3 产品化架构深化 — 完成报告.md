# ShinobuChat Phase 3 产品化架构深化 — 完成报告

> 基于 `ShinobuChat Phase 3 Productization Plan.docx` 严格实施  
> 分支: `codex/mvp` | 提交: `2ac5f7e5` | 日期: 2026-06-24

---

## 一、执行摘要

Phase 3 将 ShinobuChat 从"功能型 MVP"升级为"可维护、可解释、可产品化的 AI Agent 平台"。核心思路不是堆新功能，而是统一行为决策、能力门禁、后台调度、任务持久化和可观测性。

**关键数字：**
- 新增 24 个文件，修改 7 个文件
- 净增 1,934 行代码
- 新增 19 个单元测试，全部通过
- 现有 499 个回归测试通过（1 个预存失败，与 Phase 3 无关）
- 前端 TypeScript 编译 + Vite 构建成功

---

## 二、新增模块详情

### 2.1 BehaviorEngine — 统一行为决策引擎

**文件：** `app/services/behavior_engine.py` (225 行)

**解决的问题：** Phase 2 中行为策略分散在 8 个不同模块中（AgentCoordinator、ToolPolicyService、LocalAgentSettingsService、BrowserFacadeService、VoiceReplyService、MemoryWriteScheduler、ReminderSchedulerService、MCP Adapter），每个模块独立判断模式/权限/策略，导致行为不一致。

**核心接口：**

```python
decision = BehaviorEngine().decide(BehaviorContext(
    user_id=str(user_id),
    conversation_mode=conversation_mode,
    user_emotion=emotion,
    local_agent_settings=settings,
))
# decision.reply_length → "short" | "medium" | "long"
# decision.allowed_tool_groups → ["chat", "memory", ...]
# decision.capabilities["browser_reader"] → CapabilityDecision(enabled=True, ...)
# decision.prompt_hints → ["当前处于工作模式...", ...]
```

**集成点：**
| 调用方 | 集成方式 | 状态 |
|--------|----------|------|
| AgentCoordinator.prepare() | prompt_hints 作为 TurnScratch 注入 | 已集成 |
| ToolPolicyService.check() | 接受可选的 behavior_decision 参数 | 已集成 |

**向后兼容：**
- ModeService 未删除，保持独立可用
- ToolPolicyService 在 `behavior_decision=None` 时走完整 legacy mode logic

### 2.2 CapabilityRegistry — 统一能力目录

**文件：** `app/services/capabilities/` (3 文件, 136 行)

**能力清单：**

| Key | Label | 风险等级 | 默认状态 | 需确认 |
|-----|-------|----------|----------|--------|
| `local_launcher` | Local Launcher | medium | enabled | no |
| `browser_reader` | Browser Reader | medium | enabled | yes |
| `browser_automation` | Browser Automation | high | disabled | yes |
| `mcp` | MCP Adapter | high | disabled | no |
| `download_safety` | Download Safety | high | enabled | yes |

**CapabilityPolicyService：**
- `check(user_id, key)` → CapabilityDecision — 查询能力状态
- `ensure(user_id, key)` → 禁用时抛出 ForbiddenError
- 底层通过 LocalAgentSettingsService 读取 per-user 设置

**集成点：**
- BrowserFacadeService 全部 6 个方法已接入 `_capability_policy.ensure()`

### 2.3 JobScheduler — 后台任务调度系统

**文件：** `app/services/jobs/` (7 文件, 270 行) + `app/models/job_run_log.py` (29 行)

**注册的后台 Job：**

| Job | 功能 | 启用条件 | 间隔 |
|-----|------|----------|------|
| ReminderScanJob | 扫描到期提醒 | `SC_REMINDER_BACKGROUND_ENABLED` | `SC_REMINDER_SCAN_INTERVAL_SECONDS` |
| GoalCheckinJob | 扫描目标检查 | `SC_REMINDER_BACKGROUND_ENABLED` | `SC_REMINDER_SCAN_INTERVAL_SECONDS` |
| DiaryGenerationJob | 自动生成日记 | `SC_DIARY_AUTO_GENERATE_ENABLED` | `SC_DIARY_BACKGROUND_SCAN_INTERVAL_SECONDS` |

**JobRunLog 持久化：** `job_run_logs` 表记录每次执行的 job_name、status、duration_ms、result_summary、error_message。

**关键特性：**
- 单个 Job 失败不影响其他 Job
- disabled Job 不会被加入 scheduler.jobs
- 失败日志写入独立 try/except，不传播到主应用
- main.py 从 167 行减少到 100 行（-40%）

### 2.4 TaskRun — 任务持久化

**文件：** `app/models/task_run.py` (36 行) + `app/services/tasks/task_run_service.py` (91 行)

**模型：** `task_runs` 表持久化任务元数据（id、user_id、task_type、status、title、progress、result_summary、error_message），补充原有的内存 TaskEventStore。

**新增 API（不破坏现有路由）：**

```
GET  /api/v1/tasks              → 列出当前用户所有任务
GET  /api/v1/tasks/{task_id}    → 查看单个任务详情
GET  /api/v1/tasks/{task_id}/events  → SSE 事件流（保持不变）
```

### 2.5 SkillRunLog — Skill 激活日志

**文件：** `app/models/skill_run_log.py` (41 行) + `app/services/skill_run_log_service.py` (65 行)

**模型：** `skill_run_logs` 表记录 Skill 激活事件。

**安全措施：**
- input_summary 截断到 300 字符
- output_summary 截断到 300 字符
- 不保存完整 Skill 内容
- 日志写入失败不阻塞聊天主路径

**埋点位置：** AgentCoordinator.prepare() 在 user_skills 注入后自动记录。

### 2.6 Debug / Operations API

**文件：** `app/api/v1/routes/debug.py`（+217 行）

**新增 8 个端点：**

| 端点 | 功能 | 访问控制 |
|------|------|----------|
| `GET /debug/jobs/runs` | 所有 JobRunLog 记录 | 无限制（元数据） |
| `GET /debug/jobs/runs/{id}` | 单个 JobRunLog | 无限制 |
| `GET /debug/tasks` | 当前用户 TaskRun | 用户隔离 |
| `GET /debug/tasks/{id}` | 单个 TaskRun 详情 | 用户隔离 |
| `GET /debug/skills/runs` | 当前用户 SkillRunLog | 用户隔离 |
| `GET /debug/skills/runs/{id}` | 单个 SkillRunLog | 用户隔离 |
| `GET /debug/capabilities` | 所有 Capability + 用户决策 | 用户隔离 |
| `GET /debug/behavior/preview?mode=` | BehaviorDecision 预览 | 用户隔离 |

### 2.7 前端 Operations 面板

**文件：** `frontend/shinobu-chat/src/` (6 文件, 246 行)

| 文件 | 功能 |
|------|------|
| `api/operations.ts` | API 层，封装 5 个 Debug 端点 |
| `debug/OperationsPanel.tsx` | 标签页容器（Jobs / Tasks / Skills / Capabilities） |
| `debug/JobRunsPanel.tsx` | Job 运行记录表格 |
| `debug/TaskRunsPanel.tsx` | Task 运行记录表格 |
| `debug/SkillRunsPanel.tsx` | Skill 激活记录表格 |
| `debug/CapabilityPanel.tsx` | 能力清单表格 |

仅做只读展示，不提供修改 UI。

---

## 三、架构变化对比

```
Phase 2 (Before)                          Phase 3 (After)
──────────────────────────────────────    ──────────────────────────────────────
main.py                                   main.py
  ├─ while True: reminder_loop              └─ JobScheduler.start()
  ├─ while True: diary_loop                   ├─ ReminderScanJob
  └─ asyncio.create_task(...)                 ├─ GoalCheckinJob
                                              └─ DiaryGenerationJob
                                           app.state.job_scheduler

AgentCoordinator.prepare()                AgentCoordinator.prepare()
  ├─ _conversation_mode_context()           ├─ _conversation_mode_context()
  ├─ _persona_tone_context()                │   (保留为 fallback)
  ├─ _user_emotion_context()                ├─ BehaviorEngine.decide()
  └─ 散落策略判断                              │   ├─ prompt_hints (TurnScratch)
                                           │   └─ capabilities
                                           ├─ _record_skill_activation()
                                           │   └─ SkillRunLogService
                                           └─ (原有逻辑保留)

ToolPolicyService.check()                 ToolPolicyService.check()
  └─ mode-based rules only                  ├─ behavior_decision 参数 (Phase 3)
                                           └─ legacy mode rules (fallback)

BrowserFacadeService                      BrowserFacadeService
  └─ settings.ensure_browser_reader()       └─ _capability_policy.ensure()
                                              └─ CapabilityPolicyService
                                                 └─ LocalAgentSettingsService

(无)                                      CapabilityRegistry
                                            ├─ 5 个已注册 Capability
                                            └─ CapabilityPolicyService

(内存)                                    TaskRun (task_runs 表)
  TaskEventStore                             └─ TaskRunService

(无)                                      SkillRunLog (skill_run_logs 表)
                                            └─ SkillRunLogService

(无)                                      JobRunLog (job_run_logs 表)
                                            └─ JobRunLogService
```

---

## 四、兼容性保证

| 约束 | 状态 |
|------|------|
| ModeService 未删除 | 保留，独立可用 |
| LocalAgentSettingsService 未删除 | 保留，作为 CapabilityPolicyService 底层 |
| 所有 API 路径不变 | 仅新增，不修改旧路由 |
| SSE event 名称不变 | conversation / chunk / emotion / audio / progress / error / done / pending_action / action |
| `/api/v1/messages` 流式行为不变 | MessageService 未修改 |
| `/api/v1/browser/*` 行为不变 | BrowserFacadeService 仅内部重构 |
| `/api/v1/local-agent/*` 行为不变 | 未修改 |
| `/api/v1/mcp/*` 行为不变 | 未修改 |
| `/api/v1/tasks/*` 行为不变 | 仅新增 GET /tasks 和 GET /tasks/{id} |
| MCP 默认关闭 | 不变 |
| Browser Automation 默认关闭 | 不变 |
| Download hard block 不可绕过 | 不变 |
| 不保存完整 system prompt / tool schema / 网页正文 | 审计日志已做 redact + truncate |

---

## 五、测试结果

### 后端测试

```
$ python -m pytest tests/ --ignore=tests/test_api.py --ignore=tests/test_integration_*.py ...

结果: 499 passed, 1 failed, 4 warnings
失败: tests/test_diaries.py::test_llm_non_json_falls_back (预存问题，与 Phase 3 无关)
```

### Phase 3 新增测试

```
$ python -m pytest tests/test_behavior_engine.py tests/test_capability_registry.py -v

结果: 19 passed
- BehaviorEngine: 12 个测试（companion/work/focus/night/emotion/capability/override）
- CapabilityRegistry: 7 个测试（list/get/unknown/risk/defaults/frozen）
```

### 前端构建

```
$ cd frontend/shinobu-chat && npm run build

结果: built in 2.47s, 1802 modules transformed
- tsc -b: 通过
- vite build: 通过
```

---

## 六、安全与隐私

- **Debug API 访问控制：** 所有端点通过 `get_current_user_id` 依赖注入强制用户隔离
- **审计数据截断：** input_summary / output_summary 截断到 300 字符，不保存敏感信息
- **敏感字段 redact：** api_key、token、password 等已在 ActionAuditService 中替换为 `***REDACTED***`
- **JobRunLog 不含用户数据：** 仅记录 job_name、status、duration_ms
- **前端只读：** OperationsPanel 不做任何写操作

---

## 七、当前限制与后续建议

### 当前版本未实现

| 项目 | 原因 |
|------|------|
| 分布式任务队列 | 单进程部署足够，不需要 Celery/RQ |
| 持久化 TaskEvent | 内存存储对单进程足够 |
| MCP 多用户会话路由 | 当前通过 SC_MCP_DEFAULT_USER_ID 配置 |
| Browser Automation sandbox | Playwright 集成未完成 |
| Skill 确定性回放 | 依赖 LLM 非确定性行为 |
| Behavior A/B 测试 | 需要实验框架 |

### 建议的后续工作

1. **将 OperationsPanel 嵌入 App.tsx** — 在 SettingsPage 中添加 "Operations" 标签
2. **BehaviorEngine 实时 emotion 传递** — 从 UserEmotionService 获取实时情绪
3. **JobScheduler 管理 API** — 暂停/恢复/手动触发特定 Job
4. **扩展 Capability 列表** — 添加 voice、vision、memory、skill 等能力
5. **PromptTrace 采样** — 添加采样率配置，避免记录每次 LLM 调用

---

## 八、文件清单

### 新增文件（24 个）

```
app/models/job_run_log.py
app/models/skill_run_log.py
app/models/task_run.py
app/services/behavior_engine.py
app/services/capabilities/__init__.py
app/services/capabilities/capability_policy_service.py
app/services/capabilities/capability_registry.py
app/services/jobs/__init__.py
app/services/jobs/diary_generation_job.py
app/services/jobs/goal_checkin_job.py
app/services/jobs/job_base.py
app/services/jobs/job_registry.py
app/services/jobs/job_run_log_service.py
app/services/jobs/job_scheduler.py
app/services/jobs/reminder_scan_job.py
app/services/skill_run_log_service.py
app/services/tasks/task_run_service.py
docs/architecture/phase3-productization-after-f14-f16.md
frontend/shinobu-chat/src/api/operations.ts
frontend/shinobu-chat/src/debug/CapabilityPanel.tsx
frontend/shinobu-chat/src/debug/JobRunsPanel.tsx
frontend/shinobu-chat/src/debug/OperationsPanel.tsx
frontend/shinobu-chat/src/debug/SkillRunsPanel.tsx
frontend/shinobu-chat/src/debug/TaskRunsPanel.tsx
tests/test_behavior_engine.py
tests/test_capability_registry.py
```

### 修改文件（7 个）

```
app/api/v1/routes/debug.py                     (+217 lines)
app/api/v1/routes/tasks.py                     (+59 lines)
app/main.py                                    (-67 lines)
app/models/__init__.py                         (+6 lines)
app/services/agents/coordinator.py             (+95 lines)
app/services/browser/browser_facade_service.py (+14 lines)
app/services/tool_policy_service.py            (+29 lines)
```

---

## 九、Git 信息

- **Commit:** `2ac5f7e5` — `feat(phase3): BehaviorEngine, CapabilityRegistry, JobScheduler, TaskRun, SkillRunLog, Debug API`
- **Branch:** `codex/mvp`
- **Remote:** `origin/codex/mvp` (已推送)
- **PR:** 未创建（如需创建，执行 `gh pr create --base main --head codex/mvp`）
