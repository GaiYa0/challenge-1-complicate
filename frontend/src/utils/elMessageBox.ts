/** Element Plus MessageBox 用户取消或关闭时 reject 的值（不同版本可能略有差异） */
export function isMessageBoxDismiss(e: unknown): boolean {
  if (e === 'cancel' || e === 'close') return true
  if (typeof e === 'string') return e === 'cancel' || e === 'close'
  return false
}
