# Backend Codex Progress

## B12 — Mode Behavior Implementation (2026-06-23)

### 完成内容

- 扩展 `ModeService` 添加完整行为策略：prompt 片段 / tool policy / reply policy / reminder policy / decision tendency
- `ContextManager.roleplay_system_prompt()` 支持 `mode_section` 参数
- `RoleplayService.generate_reply()` 支持 `mode_section` 参数，注入模式感知 prompt
- `DecisionService.decide()` 支持 `mode` 参数，注入模式感知路由指令
- `ReminderSchedulerService` 支持模式感知提醒过滤和消息语调
- `main.py` + `deps.py` 接线：ModeService → ReminderSchedulerService
- 每种模式有 5 张策略表：Tool / Reply / Reminder / Decision / Prompt
- 37 个 mode 专项测试，全部通过

### 修改文件

| 文件 | 变更 |
|------|------|
| `app/schemas/mode.py` | 新增 ModeBehaviorOut / ConversationModeResponse / 策略 schemas |
| `app/services/mode_service.py` | 添加 5 张策略表 + behavior/builder 方法 |
| `app/core/context_manager.py` | roleplay_system_prompt / decision_system_prompt 接受 mode 参数 |
| `app/services/roleplay_service.py` | generate_reply 接受 mode_section |
| `app/services/decision_service.py` | decide 接受 mode 参数，模式路由指令 |
| `app/services/reminder_scheduler_service.py` | 模式感知过滤 + 消息语调 |
| `app/main.py` | ReminderSchedulerService 接收 ModeService |
| `app/api/deps.py` | get_reminder_service 传递 ModeService |
| `app/api/v1/routes/modes.py` | 响应升级为 ConversationModeResponse |
| `tests/test_modes.py` | 37 个测试覆盖全部策略 |

### API 响应示例

```json
GET /api/v1/modes/conversation
{
  "mode": "work",
  "mode_label": "工作",
  "description": "优先整理任务、步骤和结论，回复更结构化",
  "behavior": {
    "mode": "work",
    "mode_label": "工作",
    "description": "优先整理任务、步骤和结论，回复更结构化",
    "tool_policy": {
      "allowed_tool_groups": ["chat","memory","reminder","todo","goal","web_search"],
      "blocked_tool_groups": ["shell","code_exec"]
    },
    "reply_policy": {"max_sentences":5, "style":"structured", "prioritize_conciseness":true},
    "reminder_policy": {"enabled":true, "reduce_frequency":false, "urgent_only":false, "tone":"task_oriented"},
    "decision_tendency": {"chat_weight":0.4, "agent_weight":0.6, "prefer_todo_create":true, "prefer_task_planning":true, "suppress_idle_chat":false}
  },
  "updated_at": "2026-06-23T08:00:00Z"
}
```

### 测试结果

- 312 passed, 2 warnings, 39 subtests, 0 failures

## B11 — Scaffolding Phase (2026-06-23)

### 完成内容

- 新建 5 个 DB 模型：UserModeSettings、Diary、Live2DInteraction、CharacterProfile、ConversationCharacter
- 新建 5 个 Schema 模块：mode.py、vision.py、diary.py、live2d_interaction.py、character_profile.py
- 新建 4 个 Route 模块：modes.py、vision.py、diaries.py、interactions.py
- 扩展 characters.py 路由增加 profile CRUD + conversation 角色分配
- 扩展 conversations.py 路由增加 conversation 角色管理端点
- 新建 4 个 Service：ModeService、DiaryService、Live2DInteractionService、CharacterProfileService
- 新建 4 个测试文件：test_modes.py、test_diaries.py、test_live2d_interactions.py、test_character_profiles.py
- Vision analyze 和 Diary generate 显式返回 HTTP 501

### 新增文件 (21)

| 文件 | 说明 |
|------|------|
| app/models/user_mode_settings.py | 情景模式 DB 模型 |
| app/models/diary.py | 日记 DB 模型 (UniqueConstraint: user_id, date) |
| app/models/live2d_interaction.py | Live2D 交互事件 DB 模型 |
| app/models/character_profile.py | 角色档案 + 会话角色关联 DB 模型 |
| app/schemas/mode.py | ConversationMode enum + schemas |
| app/schemas/vision.py | VisionAnalyzeResponse schema |
| app/schemas/diary.py | Diary schemas (diary_id alias) |
| app/schemas/live2d_interaction.py | Live2D interaction schemas |
| app/schemas/character_profile.py | Character profile schemas |
| app/api/v1/routes/modes.py | GET/PUT /modes/conversation |
| app/api/v1/routes/vision.py | POST /vision/analyze (501) |
| app/api/v1/routes/diaries.py | GET /diaries, GET /diaries/{date}, POST /diaries/generate (501) |
| app/api/v1/routes/interactions.py | POST /interactions/live2d |
| app/services/mode_service.py | ModeService (auto-create default) |
| app/services/diary_service.py | DiaryService (generate raises NotImplementedError) |
| app/services/live2d_interaction_service.py | Live2DInteractionService (不写入 Memory) |
| app/services/character_profile_service.py | CharacterProfileService + 会话所有权校验 |
| tests/test_modes.py | Mode 单元测试 (4) |
| tests/test_diaries.py | Diary 单元测试 (8) |
| tests/test_live2d_interactions.py | L2D Interaction 单元测试 (5) |
| tests/test_character_profiles.py | Character Profile 单元测试 (13) |

### 修改文件 (5)

| 文件 | 说明 |
|------|------|
| app/models/__init__.py | 导入 5 个新模型 |
| app/api/v1/api.py | 注册 4 个新路由 |
| app/api/v1/routes/characters.py | 追加 /profiles CRUD + /conversation PUT |
| app/api/v1/routes/conversations.py | 追加 /{id}/characters GET/PUT |
| app/api/deps.py | 新增 4 个 DI 函数 |

### API 契约 (14 端点)

| Method | Path | 状态 |
|--------|------|------|
| GET | /api/v1/modes/conversation | 已实现 |
| PUT | /api/v1/modes/conversation | 已实现 |
| POST | /api/v1/vision/analyze | **501** |
| GET | /api/v1/diaries | 已实现 |
| GET | /api/v1/diaries/{date} | 已实现 |
| POST | /api/v1/diaries/generate | **501** |
| GET | /api/v1/characters/profiles | 已实现 |
| POST | /api/v1/characters/profiles | 已实现 |
| GET | /api/v1/characters/profiles/{id} | 已实现 |
| PATCH | /api/v1/characters/profiles/{id} | 已实现 |
| DELETE | /api/v1/characters/profiles/{id} | 已实现 |
| PUT | /api/v1/characters/conversation | 已实现 |
| GET | /api/v1/conversations/{id}/characters | 已实现 |
| PUT | /api/v1/conversations/{id}/characters | 已实现 |
| POST | /api/v1/interactions/live2d | 已实现 |

### 测试结果

- 新测试: 30/30 passed (test_modes 4 + test_diaries 8 + test_live2d_interactions 5 + test_character_profiles 13)
- 全量回归: 279/279 passed, 2 warnings, 0 failures
- 跨用户隔离覆盖: 所有 4 个测试文件均包含 cross-user isolation 用例

### 已有功能保护

- constitution ✅
- PrefixCacheManager ✅
- verify_step ✅
- user_config ✅
- user_skill / Skill market ✅
- reminders ✅
- memories ✅
- persona settings ✅
- goals ✅
- user emotion service ✅
- chat main flow ✅
- 现有 /characters/active 和 /conversations/user/{user_id} 未修改 ✅

### 隐私与安全

- Live2DInteraction 写入 DB 但不写入 Memory ✅
- Vision 501 不伪造图片理解 ✅
- Diary generate 501 不编造日记 ✅
- 所有新接口使用 Depends(get_current_user_id) 鉴权 ✅
- Conversation character 操作校验 conversation.user_id ✅
- Character profile 跨用户隔离 ✅

### 遗留问题

| 问题 | 计划 |
|------|------|
| Vision analyze 无实现 | B12+ 实现 VisionClient + ImageUnderstandingService |
| Diary generate 无实现 | B12+ 实现 DiaryService.generate() + LLM 日记生成 |
| Live2D interaction feedback 为占位值 | B12+ 实现 animation/expression/message 映射逻辑 |
| 情景模式未影响 RoleplayService/DecisionService | B12 逐服务集成 mode 感知 |

### 下一阶段

B12: Mode + Vision + Diary 业务逻辑实现
