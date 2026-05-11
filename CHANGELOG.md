# 提交日志

## 2026-05-11

- 新增 iOS 初版 Xcode 工程 `ios/ShinobuChat`。
- 实现 SwiftUI 聊天界面，沿用 Web 原型的暖色背景、用户/助手气泡和路由模式切换。
- 增加 iOS SQLite 本地消息缓存，支持启动恢复、消息 upsert 和清空本地缓存。
- 接入 Device Registry 设备登录流程，调用 `/auth/device/authorize` 与 `/auth/device/token`，并从 JWT 解析用户 ID。
- 增加 APNs 权限申请、device token 接收和 `/sync/apns/register` 上报。
- 增加基础推送接收处理，支持前台展示与点击通知后的最近通知状态记录。
