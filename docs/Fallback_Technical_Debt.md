# Phase Fallback：逐用户第三方服务配置消费

> 记录日期：2026-06-22  
> 关联分支：`codex/mvp`  
> 关联任务：架构改造 + 配置/Skill 系统

## 状态

配置系统已完成（保存、读取、加密、脱敏均通过测试），主 AI 模型路径会按用户配置立即生效。但以下第三方服务尚未全部改为逐用户 runtime 实例。

## Fallback 项

| # | 服务 | 字段 | 当前行为 | 目标行为 |
|---|------|------|---------|---------|
| 1 | Edge TTS | `edge_tts_voice` | 使用全局/默认 voice | 按 user_id 读取配置，使用用户指定的 voice |
| 2 | ASR | `asr_engine` / `whisper_api_key` | 使用全局实例 | 按 user_id 读取 asr_engine 和 whisper_api_key |
| 3 | Google Search | `google_search_api_key` / `google_search_cx` | 使用全局实例 | 按 user_id 读取 api_key 和 cx |

## 影响范围

- 当前单用户部署不受影响
- 多用户场景下，不同用户无法使用独立的 TTS voice / ASR engine / Search API key
- 不影响本轮（架构改造 + 配置/Skill 系统）的完成判定

## 推荐实施顺序

```
1. Edge TTS 按 user_id 读取 edge_tts_voice
2. ASR 按 user_id 读取 asr_engine / whisper_api_key
3. Google Search 按 user_id 读取 google_search_api_key / google_search_cx
4. 增加多用户配置隔离测试
5. 避免全局实例污染不同用户配置
```

## 建议时机

在语音、搜索、多模态相关功能开发前补齐。可作为独立技术债 PR，无需与后续功能耦合。
