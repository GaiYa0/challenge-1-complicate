<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import type { UploadFile } from 'element-plus'

import { useCaseStore } from '../store/case'
import { useFileStore, type FilePreviewSnapshot, type FileSummaryItem } from '../store/modules/file.store'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import FileCard from '../components/investigation/FileCard.vue'
import CountUp from '../components/common/CountUp.vue'
import FormatTime from '../components/common/FormatTime.vue'
import { notifySuccess, notifyError } from '../utils/notify'
import { getFileExtension } from '../utils/format'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const fileStore = useFileStore()
const caseId = computed(() => Number(route.params.caseId))

const { items: files, uploading } = storeToRefs(fileStore)

const previewVisible = ref(false)
const previewData = ref<FilePreviewSnapshot | null>(null)
const previewFilename = ref('')

const footerRef = ref<HTMLDivElement | null>(null)

onMounted(async () => {
  caseStore.selectCase(caseId.value)
  await fileStore.fetchList(`case-${caseId.value}`)
})

interface FileGroup {
  key: string
  label: string
  tone: 'primary' | 'success' | 'warning' | 'info'
  items: FileSummaryItem[]
}

function groupKey(name: string): FileGroup['key'] {
  if (name.startsWith('clean_')) return 'clean'
  if (name.startsWith('feature_')) return 'feature'
  return 'source'
}

const groupedFiles = computed<FileGroup[]>(() => {
  const source: FileSummaryItem[] = []
  const clean: FileSummaryItem[] = []
  const feature: FileSummaryItem[] = []
  for (const f of files.value) {
    const k = groupKey(f.filename)
    if (k === 'clean') clean.push(f)
    else if (k === 'feature') feature.push(f)
    else source.push(f)
  }
  const groups: FileGroup[] = [
    { key: 'source', label: '原始数据', tone: 'primary', items: source },
    { key: 'clean', label: '清洗结果', tone: 'success', items: clean },
    { key: 'feature', label: '特征结果', tone: 'info', items: feature },
  ]
  return groups.filter((g) => g.items.length > 0)
})

const sourceCount = computed(() => groupedFiles.value.find((g) => g.key === 'source')?.items.length ?? 0)
const totalFileCount = computed(() => files.value.length)

const ALLOWED_EXTS = ['.csv', '.txt', '.json', '.xls', '.xlsx']

function getExt(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot >= 0 ? name.slice(dot).toLowerCase() : ''
}

async function handleUpload(file: UploadFile) {
  if (!file.raw) return
  const ext = getExt(file.raw.name)
  if (!ALLOWED_EXTS.includes(ext)) {
    notifyError(`不支持的文件格式 (${ext})，请上传 CSV / XLS / XLSX / JSON / TXT 文件`)
    return
  }
  try {
    await fileStore.upload(file.raw, { dataset: `case-${caseId.value}` })
    notifySuccess('上传成功')
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '上传失败')
  }
}

async function handlePreview(filename: string) {
  try {
    previewData.value = await fileStore.preview(filename)
    previewFilename.value = filename
    previewVisible.value = true
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '预览失败')
  }
}

async function handleRemove(filename: string) {
  try {
    await fileStore.remove(filename)
    notifySuccess('已移除')
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '移除失败')
  }
}

function goNext() {
  router.push(`/cases/${caseId.value}/cleaning`)
}

function scrollToBottom() {
  footerRef.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}
</script>

<template>
  <div class="data-import-page">
    <StepIndicator :current="1" />

    <h1 class="page-title">导入调查数据</h1>
    <p class="page-subtitle">上传与本案件相关的数据文件，清洗是后续所有分析的基础</p>

    <div class="upload-zone">
      <el-upload
        drag
        action=""
        :auto-upload="false"
        :show-file-list="false"
        accept=".csv,.txt,.json,.xls,.xlsx"
        :disabled="uploading"
        @change="handleUpload"
      >
        <div class="upload-inner">
          <p class="upload-text">将数据文件拖拽到此处，或点击选择文件</p>
          <p class="upload-hint">支持 CSV / XLS / XLSX / JSON / TXT 格式；上传后将自动进入数据处理流水线</p>
        </div>
      </el-upload>
    </div>

    <div class="summary-bar" v-if="files.length > 0">
      <div class="summary-item">
        <span class="summary-value"><CountUp :value="totalFileCount" /></span>
        <span class="summary-label">文件总数</span>
      </div>
      <div class="summary-item">
        <span class="summary-value"><CountUp :value="sourceCount" /></span>
        <span class="summary-label">可用原始数据</span>
      </div>
      <div v-if="sourceCount === 0" class="summary-warning">
        尚无可用原始数据，派生结果不能进入下一步清洗
      </div>
      <el-button
        v-if="totalFileCount > 10"
        text
        class="scroll-bottom-btn"
        @click="scrollToBottom"
      >
        快速定位到底部
      </el-button>
    </div>

    <div ref="fileListRef">
      <template v-if="files.length > 0">
        <div v-for="group in groupedFiles" :key="group.key" class="file-group">
          <div class="file-group-head">
            <span class="file-group-title">{{ group.label }}</span>
            <el-tag :type="group.tone" size="small" effect="plain">{{ group.items.length }}</el-tag>
            <span v-if="group.key !== 'source'" class="file-group-hint">
              由系统自动生成，不参与新一轮清洗
            </span>
          </div>
          <div class="file-list-items">
            <FileCard
              v-for="f in group.items"
              :key="f.filename"
              :filename="f.filename"
              :upload-time="f.upload_time"
              :tags="[getFileExtension(f.filename).toUpperCase()]"
              @preview="handlePreview(f.filename)"
              @remove="handleRemove(f.filename)"
            />
          </div>
        </div>
      </template>

      <div v-else class="empty-state">
        <p class="empty-text">还没有导入数据</p>
        <p class="empty-hint">拖拽文件到上方区域，即可开始</p>
      </div>
    </div>

    <div ref="footerRef" class="page-footer">
      <el-button
        type="primary"
        size="large"
        :disabled="sourceCount === 0"
        @click="goNext"
      >
        下一步：数据清洗
      </el-button>
    </div>

    <el-dialog v-model="previewVisible" :title="`数据预览 - ${previewFilename}`" width="720px">
      <div v-if="previewData" style="overflow-x: auto;">
        <el-table :data="previewData.preview" max-height="400" size="small" border stripe>
          <el-table-column
            v-for="col in previewData.columns"
            :key="col"
            :prop="col"
            :label="col"
            min-width="120"
          />
        </el-table>
        <p class="preview-hint">
          共 {{ previewData.preview.length }} 行预览 -
          <FormatTime :value="Date.now()" pattern="HH:mm:ss" :show-relative="false" />
        </p>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.data-import-page { max-width: 920px; margin: 0 auto; }
.page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--app-text);
  margin: 0 0 4px;
  text-align: center;
}
.page-subtitle {
  font-size: 14px;
  color: var(--app-text-secondary);
  text-align: center;
  margin: 0 0 28px;
}
.upload-zone {
  margin-bottom: 24px;
}
.upload-zone :deep(.el-upload-dragger) {
  padding: 48px 20px;
  border-radius: var(--app-radius);
  border: 2px dashed var(--app-border);
  background: var(--app-bg-card);
  transition: border-color 0.18s ease;
}
.upload-zone :deep(.el-upload-dragger:hover) {
  border-color: var(--app-primary);
}
.upload-inner { text-align: center; }
.upload-text {
  font-size: 16px;
  color: var(--app-text);
  margin: 0 0 4px;
}
.upload-hint {
  font-size: 13px;
  color: var(--app-text-secondary);
  margin: 0;
}
.summary-bar {
  display: flex;
  align-items: center;
  gap: 32px;
  padding: 16px 20px;
  margin-bottom: 20px;
  background: var(--app-bg-card);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  box-shadow: var(--app-shadow-card);
  flex-wrap: wrap;
}
.summary-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.summary-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--app-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}
.summary-label {
  font-size: 12px;
  color: var(--app-text-secondary);
}
.summary-warning {
  font-size: 13px;
  color: var(--app-warning);
}
.scroll-bottom-btn {
  margin-left: auto;
}
.file-group {
  margin-bottom: 20px;
}
.file-group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 10px;
}
.file-group-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--app-text);
}
.file-group-hint {
  margin-left: auto;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.file-list-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.empty-state {
  text-align: center;
  padding: 60px 16px;
  background: var(--app-bg-card);
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius);
}
.empty-text {
  font-size: 18px;
  color: var(--app-text);
  margin: 0 0 6px;
  font-weight: 600;
}
.empty-hint {
  font-size: 14px;
  color: var(--app-text-secondary);
  margin: 0;
}
.preview-hint {
  font-size: 12px;
  color: var(--app-text-secondary);
  margin: 8px 0 0;
}
.page-footer {
  text-align: center;
  margin-top: 36px;
  padding-bottom: 20px;
}
</style>
