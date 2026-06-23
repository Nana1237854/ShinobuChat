# Phase 3 产品化架构深化 — 完成报告

## 概述

基于 F14-F16 功能模块完成后的架构深化，将项目从"功能型 MVP"升级为"可维护、可解释、可产品化的 AI Agent 平台"。

## Phase 3 新增模块

### 1. BehaviorEngine (`app/services/behavior_engine.py`)

统一行为决策引擎，替代分散在以下模块中的模式/策略逻辑：
- AgentCoordinator.conversation_mode_context()
- ToolPolicyService 的模式规则
- LocalAgentSettingsService 权限门禁
- VoiceReplyService TTS 风格选择
- MemoryWriteScheduler 记忆策略

**核心数据结构：**
- `BehaviorContext` — 传入决策上下文（user_id、conversation_mode、emotion、settings 等）
- `BehaviorDecision` — 输出统一决策（reply_length、tool groups、capabilities、prompt_hints 等）
- `CapabilityDecision` — 单项能力门禁结果

**集成点：**
- AgentCoordinator.prepare() 调用 BehaviorEngine.decide()
- ToolPolicyService.check() 接受可选的 BehaviorDecision 参数
- prompt_hints 作为 TurnScratch 注入，不写入 PinnedPrefix

**向后兼容：**
- ModeService 保持独立可用
- LocalAgentSettingsService 保持独立可用
- BehaviorEngine 通过调用 ModeService 的 Policy tables 获取模式数据
- ToolPolicyService 在 behavior_decision=None 时走 legacy mode logic

### 2. CapabilityRegistry (`app/services/capabilities/`)

统一能力目录和权限门禁。

**Capability 列表：**
| Key | Label | Risk | Default |
|-----|-------|------|---------|
| local_launcher | Local Launcher | medium | enabled |
| browser_reader | Browser Reader | medium | enabled |
| browser_automation | Browser Automation | high | disabled |
| mcp | MCP Adapter | high | disabled |
| download_safety | Download Safety | high | enabled |

**CapabilityPolicyService：**
- `check(user_id, key)` — 查询单项能力状态
- `ensure(user_id, key)` — 禁用时抛出 ForbiddenError
- 底层调用 LocalAgentSettingsService 读取 per-user 设置

**集成点：**
- BrowserFacadeService 已接入 CapabilityPolicyService
- MCP status 和 LocalAppService 可随时接入

### 3. JobScheduler (`app/services/jobs/`)

统一后台任务调度，替代 main.py 中的裸 `while True` 循环。

**注册的 Job：**
| Job | Interval | Enabled | 功能 |
|-----|----------|---------|------|
| ReminderScanJob | SC_REMINDER_SCAN_INTERVAL_SECONDS | SC_REMINDER_BACKGROUND_ENABLED | 扫描到期提醒 |
| GoalCheckinJob | SC_REMINDER_SCAN_INTERVAL_SECONDS | SC_REMINDER_BACKGROUND_ENABLED | 扫描目标检查 |
| DiaryGenerationJob | SC_DIARY_BACKGROUND_SCAN_INTERVAL_SECONDS | SC_DIARY_AUTO_GENERATE_ENABLED | 自动生成日记 |

**JobRunLog 模型：**
- `job_run_logs` 表记录每次 job 执行的元数据
- 记录成功/失败状态、执行时长、结果摘要
- Job 失败不传播到主应用，不阻塞其他 Job

**main.py 变更：**
- startup_event() 从直接创建 while 循环改为创建 JobScheduler.start()
- shutdown_event() 新增 JobScheduler.stop()
- app.state.job_scheduler 存储调度器引用

### 4. Task System 产品化 (`app/models/task_run.py`, `app/services/tasks/task_run_service.py`)

**TaskRun 模型：**
- `task_runs` 表持久化任务执行元数据
- 补充原有的内存 TaskEventStore，提供持久化记录

**新增 API：**
- `GET /api/v1/tasks` — 列出当前用户的所有任务
- `GET /api/v1/tasks/{task_id}` — 查看单个任务详情
- `GET /api/v1/tasks/{task_id}/events` — SSE 事件流（保持不变）

### 5. SkillRunLog (`app/models/skill_run_log.py`, `app/services/skill_run_log_service.py`)

**SkillRunLog 模型：**
- `skill_run_logs` 表记录 Skill 激活/执行事件
- 包含 input_summary、output_summary（截断到 300 字符）
- 不保存完整 Skill 内容

**埋点位置：**
- AgentCoordinator.prepare() 在 runtime skills 激活时记录
- 未来可在 activate_skill tool、Skill market install 等处扩展

### 6. Debug / Operations API

**新增端点：**
| 端点 | 功能 |
|------|------|
| `GET /api/v1/debug/jobs/runs` | 列出所有 JobRunLog 记录 |
| `GET /api/v1/debug/jobs/runs/{run_id}` | 查看单个 JobRunLog |
| `GET /api/v1/debug/tasks` | 列出当前用户 TaskRun（安全摘要） |
| `GET /api/v1/debug/tasks/{task_id}` | 查看单个 TaskRun |
| `GET /api/v1/debug/skills/runs` | 列出当前用户 SkillRunLog |
| `GET /api/v1/debug/skills/runs/{run_id}` | 查看单个 SkillRunLog |
| `GET /api/v1/debug/capabilities` | 列出所有 Capability + 当前用户决策 |
| `GET /api/v1/debug/behavior/preview?mode=` | 预览指定模式的 BehaviorDecision |

**安全约束：**
- 所有端点仅返回当前用户数据
- 不保存完整 system prompt、tool schema、网页正文或 API key

### 7. 前端 Operations 面板

**新增文件：**
- `frontend/shinobu-chat/src/api/operations.ts` — API 层
- `frontend/shinobu-chat/src/debug/OperationsPanel.tsx` — 标签页容器
- `frontend/shinobu-chat/src/debug/JobRunsPanel.tsx` — Job 运行记录
- `frontend/shinobu-chat/src/debug/TaskRunsPanel.tsx` — Task 运行记录
- `frontend/shinobu-chat/src/debug/SkillRunsPanel.tsx` — Skill 运行记录
- `frontend/shinobu-chat/src/debug/CapabilityPanel.tsx` — 能力清单

仅做只读展示，不提供修改 UI。

## 兼容性说明

- **ModeService 未删除** — 保持独立运行，BehaviorEngine 通过其 Policy tables 获取数据
- **LocalAgentSettingsService 未删除** — 保持独立运行，CapabilityPolicyService 通过其读取设置
- **所有 API 路径不变** — 仅新增，不修改旧路由
- **所有 SSE event 名称不变**
- **`/api/v1/messages` 流式聊天行为不变**
- **`/api/v1/browser/*`、`/api/v1/local-agent/*`、`/api/v1/mcp/*`、`/api/v1/tasks/*` 行为不变**
- **MCP 默认关闭、Browser Automation 默认关闭、Download hard block 不可绕过**

## 限于当前阶段未实现

- 分布式任务队列（当前不需要）
- 持久化 TaskEvent（内存存储对单进程足够）
- MCP 多用户会话路由
- Browser Automation sandbox
- Skill 确定性回放
- Behavior A/B 测试

## 下一阶段建议

1. 将 CapabilityDecision 序列化为 JSON 兼容格式（dataclass → dict）
2. 为 BehaviorEngine、JobScheduler、TaskRunService 补单元测试
3. 将 OperationsPanel 嵌入 App.tsx settings 标签
4. 考虑为 JobScheduler 添加暂停/恢复 API
5. 考虑为 PromptTrace 添加采样率配置（避免记录每次调用）
