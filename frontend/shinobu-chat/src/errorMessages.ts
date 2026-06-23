const ERROR_MESSAGES: Record<number, string> = {
  400: '请求参数有误',
  401: '请先登录',
  403: '没有权限',
  404: '资源不存在或无权访问',
  409: '资源冲突或名称重复',
  413: '图片过大，请压缩后重试',
  429: '操作太频繁，请稍后再试',
  500: '服务器内部错误',
  502: '图片理解服务暂时不可用，已尝试 OCR 备用识别',
  503: '图片理解服务暂时不可用，已尝试 OCR 备用识别',
};

export function getErrorMessage(status: number, fallback: string): string {
  return ERROR_MESSAGES[status] ?? fallback;
}
