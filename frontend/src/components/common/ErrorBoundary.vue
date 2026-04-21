<script setup lang="ts">
/**
 * 全局错误边界（组件级）：捕获子树 `errorCaptured`，渲染可重试的兜底 UI。
 * - 不能吞掉网络层 4xx/5xx，那些仍旧走 axios 拦截器 + notify。
 * - 主要兜底：组件内同步异常 / watch 回调异常 / setup 抛错。
 */
import { nextTick, onErrorCaptured, ref } from 'vue'

const hasError = ref(false)
const message = ref<string>('')
const stack = ref<string>('')

onErrorCaptured((err, _instance, info) => {
  hasError.value = true
  if (err instanceof Error) {
    message.value = err.message || '页面渲染异常'
    stack.value = `[${info}]\n${err.stack ?? ''}`
  } else {
    message.value = String(err ?? '页面渲染异常')
    stack.value = `[${info}]`
  }
  console.error('[ErrorBoundary]', err, info)
  return false
})

async function retry() {
  hasError.value = false
  message.value = ''
  stack.value = ''
  await nextTick()
}
</script>

<template>
  <div v-if="hasError" class="error-boundary">
    <el-result
      icon="warning"
      title="页面出错了"
      :sub-title="message"
    >
      <template #extra>
        <el-button type="primary" @click="retry">重试加载</el-button>
        <el-button @click="$router?.push?.('/cases')">返回案件列表</el-button>
      </template>
    </el-result>
    <details v-if="stack" class="error-stack no-print">
      <summary>调试信息</summary>
      <pre>{{ stack }}</pre>
    </details>
  </div>
  <slot v-else />
</template>

<style scoped>
.error-boundary {
  padding: 24px 0;
}
.error-stack {
  max-width: 820px;
  margin: 16px auto 0;
  padding: 12px 16px;
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  font-size: 12px;
  color: var(--app-text-secondary);
}
.error-stack pre {
  white-space: pre-wrap;
  word-break: break-all;
  margin: 8px 0 0;
}
</style>
