<script setup lang="ts">
import { ref, onBeforeUnmount, watch } from 'vue'

const props = defineProps<{
  running: boolean
  messages?: string[]
  progress?: number
}>()

const defaultMessages = [
  '正在读取数据...',
  '正在检测异常交易...',
  '正在分析资金流向...',
  '正在生成分析结果...',
]

const currentIdx = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

function startRotation() {
  currentIdx.value = 0
  timer = setInterval(() => {
    const msgs = props.messages ?? defaultMessages
    currentIdx.value = (currentIdx.value + 1) % msgs.length
  }, 4000)
}

function stopRotation() {
  if (timer) { clearInterval(timer); timer = null }
}

watch(() => props.running, (v) => {
  if (v) startRotation()
  else stopRotation()
}, { immediate: true })

onBeforeUnmount(stopRotation)
</script>

<template>
  <div v-if="running" class="analysis-progress">
    <div class="progress-spinner" />
    <p class="progress-message">{{ (messages ?? defaultMessages)[currentIdx] }}</p>
    <div v-if="progress !== undefined && progress >= 0" class="progress-bar-wrap">
      <div class="progress-bar" :style="{ width: progress + '%' }" />
    </div>
    <p v-if="progress !== undefined && progress >= 0" class="progress-pct">{{ progress }}%</p>
  </div>
</template>

<style scoped>
.analysis-progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 0;
}
.progress-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid #e5e7eb;
  border-top-color: var(--app-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.progress-message {
  font-size: 16px;
  color: var(--app-text);
  margin: 0 0 20px;
}
.progress-bar-wrap {
  width: 320px;
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  background: var(--app-primary);
  border-radius: 4px;
  transition: width 0.5s ease;
}
.progress-pct {
  font-size: 13px;
  color: var(--app-text-secondary);
  margin: 8px 0 0;
}
</style>
