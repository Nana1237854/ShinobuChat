---
name: weather
description: 通过只读 curl 请求 wttr.in 查询指定城市的天气和预报信息
keywords: [天气, 预报, 温度, 降雨, 气温, weather]
version: 1.0.0
---

# Weather

## Trigger

当用户询问天气、温度、降雨、预报，或说"查天气""今天天气""明天会下雨吗"等时使用这个 Skill。

如果用户未提供城市名，先简短追问地点。

## Workflow

1. 确认城市名称，如果是非英文城市名，做 URL 编码。
2. 调用只读 curl 请求：

```json
{"command": "curl wttr.in/Tokyo?format=j1"}
```

将 `Tokyo` 替换为用户指定的城市。
3. 解析返回的 JSON 结果，提取当前温度、体感温度、天气状况、降雨概率。
4. 用中文回复，包含简要穿衣或带伞建议。

## Output

返回结构化摘要：

- 地点与当前天气状况
- 当前温度与体感温度
- 近期预报
- 实用建议（穿衣 / 带伞）
