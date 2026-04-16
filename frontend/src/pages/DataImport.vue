<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCaseStore } from '../store/case'
import { uploadFile as uploadFileApi, listDbFiles, getFilePreview, deleteFileByName } from '../api/file'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import FileCard from '../components/investigation/FileCard.vue'
import { notifySuccess, notifyError } from '../utils/notify'
import type { UploadFile } from 'element-plus'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const caseId = computed(() => Number(route.params.caseId))

interface FileItem {
  filename: string
  upload_time?: string
}

const files = ref<FileItem[]>([])
const uploading = ref(false)
const previewVisible = ref(false)
const previewData = ref<{ columns: string[]; preview: unknown[] } | null>(null)

onMounted(async () => {
  caseStore.selectCase(caseId.value)
  await loadFiles()
})

async function loadFiles() {
  try {
    const all = (await listDbFiles()) as unknown as { filename: string; upload_time?: string }[]
    files.value = all
  } catch {
    files.value = []
  }
}

async function handleUpload(file: UploadFile) {
  if (!file.raw) return
  uploading.value = true
  try {
    await uploadFileApi(file.raw, { dataset: `case-${caseId.value}` })
    notifySuccess('上传成功')
    await loadFiles()
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '上传失败')
  } finally {
    uploading.value = false
  }
}

async function handlePreview(filename: string) {
  try {
    const data = (await getFilePreview(filename)) as unknown as { columns: string[]; preview: unknown[] }
    previewData.value = data
    previewVisible.value = true
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '预览失败')
  }
}

async function handleRemove(filename: string) {
  try {
    await deleteFileByName(filename)
    notifySuccess('已移除')
    await loadFiles()
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '移除失败')
  }
}

function goNext() {
  router.push(`/cases/${caseId.value}/analyze`)
}
</script>

<template>
  <div class="data-import-page">
    <StepIndicator :current="1" />

    <h1 class="page-title">导入调查数据</h1>
    <p class="page-subtitle">上传与本案件相关的数据文件</p>

    <div class="upload-zone">
      <el-upload
        drag
        action=""
        :auto-upload="false"
        :show-file-list="false"
        accept=".csv,.txt,.json"
        @change="handleUpload"
      >
        <div class="upload-inner">
          <div class="upload-icon">&#128228;</div>
          <p class="upload-text">将数据文件拖拽到此处，或点击选择文件</p>
          <p class="upload-hint">支持 CSV、文本等格式</p>
        </div>
      </el-upload>
    </div>

    <div v-if="files.length > 0" class="file-list">
      <h3 class="section-title">已导入的数据文件</h3>
      <div class="file-list-items">
        <FileCard
          v-for="f in files"
          :key="f.filename"
          :filename="f.filename"
          :upload-time="f.upload_time"
          @preview="handlePreview(f.filename)"
          @remove="handleRemove(f.filename)"
        />
      </div>
    </div>

    <div class="page-footer">
      <el-button type="primary" size="large" :disabled="files.length === 0" @click="goNext">
        下一步：开始分析 &rarr;
      </el-button>
    </div>

    <el-dialog v-model="previewVisible" title="数据预览" width="700px">
      <div v-if="previewData" style="overflow-x: auto;">
        <el-table :data="(previewData.preview as Record<string, unknown>[])" max-height="400" size="small">
          <el-table-column
            v-for="col in previewData.columns"
            :key="col"
            :prop="col"
            :label="col"
            min-width="120"
          />
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.data-import-page { max-width: 800px; margin: 0 auto; }
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
  margin-bottom: 32px;
}
.upload-zone :deep(.el-upload-dragger) {
  padding: 48px 20px;
  border-radius: var(--app-radius);
  border: 2px dashed var(--app-border);
}
.upload-inner { text-align: center; }
.upload-icon { font-size: 48px; margin-bottom: 12px; }
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
.section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--app-text);
}
.file-list-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.page-footer {
  text-align: center;
  margin-top: 36px;
  padding-bottom: 20px;
}
</style>
