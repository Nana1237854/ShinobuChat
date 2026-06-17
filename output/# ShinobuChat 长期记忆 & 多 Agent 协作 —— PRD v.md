# ShinobuChat 长期记忆 & 多 Agent 协作 —— PRD v1.0

**日期:** 2026-06-17
**目标:** 为课程论文提供第三、四、五章的实践内容支撑

---

## 一、长期记忆模块（RAG 知识增强）

### 1.1 功能概述

用户与 AI 对话后，系统自动提取关键信息存入向量数据库。后续对话中，根据用户问题检索相关记忆，增强 AI 回复。

### 1.2 核心流程

```
用户消息 → Embedding 向量化 → pgvector 检索 Top-3 相似记忆
  → 注入 AI System Prompt（作为上下文）
  → AI 生成回复时参考历史记忆
  → 异步提取本轮对话要点 → 写入向量库
```

### 1.3 数据模型

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | UUID | 主键 |
| `user_id` | UUID FK | 归属用户 |
| `content` | Text | 记忆内容（摘要） |
| `embedding` | vector(768) | 文本嵌入向量 |
| `source_msg_id` | UUID FK | 来源消息 |
| `importance` | float | 重要性评分（0-1） |
| `created_at` | datetime | 创建时间 |

### 1.4 技术选型

| 层 | 选择 | 理由 |
|---|---|---|
| 向量数据库 | pgvector（PostgreSQL 扩展） | 已有 PG，零额外部署 |
| Embedding | DeepSeek API `/embeddings` | 复用已有 API Key |
| 检索策略 | Top-K 余弦相似度 | 简单有效，论文够用 |
| 写入时机 | 异步（每轮对话后批量写入） | 不阻塞 SSE 流 |

### 1.5 验收标准

- [ ] 对话 ≥ 3 轮后，AI 能引用之前的对话内容
- [ ] 向量检索延迟 < 200ms
- [ ] 记忆提取不阻塞 SSE 流式输出

---

## 二、多 Agent 协作模块

### 2.1 功能概述

当前只有单 Agent（tool calling）。扩展为多 Agent 协作模式：一个调度 Agent + 多个专业 Agent。

### 2.2 Agent 架构

```
用户消息
  → Router Agent（路由判断：闲聊 / 查询 / 任务）
    ├─ Chat Agent（日常陪伴，当前 RouteMode.CHAT）
    ├─ Task Agent（工具调用，当前 RouteMode.AGENT）
    └─ Memory Agent（记忆管理：提取、检索、更新）
```

### 2.3 Agent 定义

| Agent | 职责 | System Prompt 特点 |
|---|---|---|
| **Router Agent** | 意图分类，分发到子 Agent | 轻量分类，仅路由 |
| **Chat Agent** | 日常闲聊、情感陪伴 | 温暖语气，短回复 |
| **Task Agent** | 工具调用、任务执行 | 结构化思考，工具优先 |
| **Memory Agent** | 记忆 CRUD、检索 | 只处理记忆操作，不对用户直接回复 |

### 2.4 协作流程

```
1. Router 接收用户消息 → 判断意图
2. 如果是闲聊 → Chat Agent 生成回复
3. 如果是任务 → Task Agent 调用工具 → 生成回复
4. 每轮对话后 → Memory Agent 异步提取要点 → 写入向量库
5. 下次对话时 → Memory Agent 检索相关记忆 → 注入各个 Agent 的上下文
```

### 2.5 验收标准

- [ ] Router Agent 意图分类准确率 > 80%
- [ ] 各 Agent 独立运行，不共享全局状态
- [ ] Agent 间通过明确的接口（消息格式）通信

---

## 三、用户验证方案

### 3.1 验证目的

验证 ShinobuChat 在真实使用场景下的：响应延迟、语音质量、Live2D 交互体验、长期记忆效果。

### 3.2 参与用户

| 用户 | 角色 | 使用场景 |
|---|---|---|
| 用户 A（同学） | 日常聊天 | 闲聊、天气查询 |
| 用户 B（同学） | 任务场景 | Agent 模式、网页抓取 |
| 用户 C（自己） | 综合测试 | 全模式、记忆验证 |

### 3.3 验证任务

| 任务编号 | 任务描述 | 验证指标 |
|---|---|---|
| T1 | 连续 5 轮闲聊对话 | 响应延迟、语音质量、表情匹配度 |
| T2 | 使用 Agent 模式查询天气 | 工具调用成功率、回复准确性 |
| T3 | 告诉 AI 你的名字和喜好 | 下轮对话能否回忆起 |
| T4 | 语音输入 → TTS 输出完整闭环 | ASR 准确率、TTS 自然度 |
| T5 | 切换 Live2D 模型和背景 | UI 交互流畅度 |

### 3.4 数据收集

每项任务用 **5 点李克特量表**（1=非常差，5=非常好）：

| 维度 | 用户 A | 用户 B | 用户 C | 平均值 |
|---|---|---|---|---|
| 响应速度 | | | | |
| 语音自然度 | | | | |
| 表情匹配度 | | | | |
| 记忆准确度 | | | | |
| 整体满意度 | | | | |

### 3.5 验收标准

- [ ] 收集 ≥ 3 位用户反馈
- [ ] 计算各维度平均分
- [ ] 记录 ≥ 2 条改进建议

---

## 四、实现提示词

以下提示词可直接用于实现各模块。按顺序执行。

### 提示词 1：长期记忆（pgvector + RAG）

```
在 PostgreSQL 中启用 pgvector 扩展，然后实现：
1. 创建 memories 表（id, user_id, content, embedding, source_msg_id, importance, created_at）
2. 创建 MemoryService（/app/services/memory_service.py）：
   - store_memory(user_id, content, embedding) → 写入
   - search_memories(user_id, query_embedding, top_k=3) → 检索
   - extract_memories(conversation_text) → 用 AI 提取关键信息
3. 修改 MessageService：每轮对话后异步调用 extract_memories + store_memory
4. 修改 _build_ai_messages：调用 search_memories，将检索结果注入 system prompt
5. Embedding 使用 DeepSeek API /embeddings 端点
6. 配置项：SC_MEMORY_PGVECTOR_ENABLED=true, SC_MEMORY_MAX_RESULTS=3
```

### 提示词 2：多 Agent 协作

```
在现有 Agent 基础上扩展多 Agent 协作：
1. 创建 app/services/agents/ 目录
2. 实现 RouterAgent（route_agent.py）：
   - 接收用户消息 → 判断意图（chat/task）
   - 返回 {"target": "chat"|"task", "confidence": 0.0-1.0}
3. 实现 ChatAgent（chat_agent.py）：
   - 复用现有 _build_ai_messages 逻辑
   - System prompt 强调温暖陪伴
4. 实现 TaskAgent（task_agent.py）：
   - 复用现有 agent_orchestrator 逻辑
   - System prompt 强调工具调用
5. 实现 MemoryAgent（memory_agent.py）：
   - 提供 extract（提取记忆）和 search（检索记忆）接口
   - 不对用户直接输出
6. 创建 AgentCoordinator（coordinator.py）：
   - 编排 Router → 子 Agent 的调用链
   - 统一的消息格式：{"role": "agent", "content": "...", "agent": "chat"}
7. 修改 MessageService：route_mode 由 RouterAgent 自动决定（不再手动选择）
```

### 提示词 3：用户验证设计

```
帮我设计一个用户验证计划：
1. 招募 3 名同学（2 名外部 + 自己）
2. 每人完成 5 项验证任务（闲聊、Agent、记忆、语音、UI）
3. 每项任务用 5 点量表评分（响应速度、语音自然度、表情匹配度、记忆准确度、整体满意度）
4. 收集改进建议
5. 生成验证报告模板（含数据表格）
```
