/** 与 axios 拦截器、Pinia userStore 共用，避免多处魔法字符串 */
export const TOKEN_STORAGE_KEY = 'access_token'

/** 多租户：与 userStore 写入、request 请求头 X-Tenant-ID 对齐 */
export const TENANT_STORAGE_KEY = 'tenant_id'
