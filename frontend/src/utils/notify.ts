import { ElMessage } from 'element-plus'

/** 统一提示：文案、时长、风格一致，业务层禁止直接散落 ElMessage */
export function notifySuccess(message: string) {
  ElMessage.success({ message, duration: 2200, showClose: true })
}

export function notifyError(message: string) {
  ElMessage.error({ message, duration: 4500, showClose: true })
}

export function notifyWarning(message: string) {
  ElMessage.warning({ message, duration: 3200, showClose: true })
}

export function notifyInfo(message: string) {
  ElMessage.info({ message, duration: 2800, showClose: true })
}

/** 业务侧可统一 `notify.success(...)` 调用，避免散落 ElMessage */
export const notify = {
  success: notifySuccess,
  error: notifyError,
  warning: notifyWarning,
  info: notifyInfo,
} as const
