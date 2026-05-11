# ShinobuChat iOS

Initial SwiftUI iOS client for the ShinobuChat backend.

## Capabilities

- SwiftUI chat screen aligned with the web prototype bubble treatment.
- Local SQLite cache for conversations and messages.
- Device Registry login through `/api/v1/auth/device/authorize` and `/api/v1/auth/device/token`.
- APNs token registration through `/api/v1/sync/apns/register`.
- Basic push notification receive hooks for foreground and tap handling.

## Run

1. Open `ShinobuChat.xcodeproj` in Xcode 15 or newer.
2. Select the `ShinobuChat` target and set a signing team.
3. Update the API base URL in the sign-in screen. Simulator-to-localhost commonly uses `http://127.0.0.1:8000/api/v1`.
4. Build and run on an iOS 17+ simulator or device.

Push notifications require a real device, an App ID with Push Notifications enabled, and the `aps-environment` entitlement set for your signing profile.
