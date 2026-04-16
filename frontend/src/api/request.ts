/**
 * @deprecated 请优先使用 `import http from './client'` 或 `api/modules/*`。
 * 保留默认导出以兼容既有 `import request from './request'`。
 */

export type { ApiEnvelope } from './envelope'
export { isApiEnvelope, extractRequestId } from './envelope'
export { default } from './client'
