<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import type { UploadFile } from 'element-plus'

import { useCaseStore } from '../store/case'
import { useFileStore, type FilePreviewSnapshot } from '../store/modules/file.store'
import StepIndicator from '../components/investigation/StepIndicator.vue'
import FileCard from '../components/investigation/FileCard.vue'
import { notifySuccess, notifyError } from '../utils/notify'

const route = useRoute()
const router = useRouter()
const caseStore = useCaseStore()
const fileStore = useFileStore()
const caseId = computed(() => Number(route.params.caseId))

const { items: files, uploading } = storeToRefs(fileStore)

const previewVisible = ref(false)
const previewData = ref<FilePreviewSnapshot | null>(null)

onMounted(async () => {
  caseStore.selectCase(caseId.value)
  await fileStore.fetchList()
})

async function handleUpload(file: UploadFile) {
  if (!file.raw) return
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
        :disabled="uploading"
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
        <el-table :data="previewData.preview" max-height="400" size="small">
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
