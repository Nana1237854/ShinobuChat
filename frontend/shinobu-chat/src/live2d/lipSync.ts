// EchoBot 口型同步参数 — 统一管理入口
// 参考: https://github.com/KdaiP/EchoBot

/**
 * Live2D 张嘴参数 ID 列表。
 * 优先匹配 Cubism4（ParamMouthOpenY），不存在则回退到 Cubism3（ParamA）。
 * SDK 会静默忽略不存在的 ID，所以列两个是安全的。
 */
export const LIP_SYNC_IDS = ['ParamMouthOpenY', 'ParamA'] as const;

/** Web Audio API 分析器 FFT 窗口大小。1024 是响应速度和平滑度的平衡点。 */
export const LIP_SYNC_FFT_SIZE = 1024;

/** 噪声底线（RMS 阈值）。低于此值的音频信号视为静音，不做口型。 */
export const LIP_SYNC_NOISE_FLOOR = 0.02;

/** 音量增益倍数（RMS → 0–1）。数值越大，同样音量下嘴巴张得越大。 */
export const LIP_SYNC_SCALE = 5.4;

/** EMA 指数移动平均平滑因子（0–1）。控制嘴巴跟随音频包络的速度。 */
export const LIP_SYNC_SMOOTHING = 0.5;

/** AudioContext 内置平滑时间常数（秒）。 */
export const ANALYSER_SMOOTHING = 0.7;
