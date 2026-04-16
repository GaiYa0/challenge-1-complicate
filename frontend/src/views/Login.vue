<script setup lang="ts">
import type { FormInstance, FormRules } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../store/user'
import { notifyError, notifySuccess } from '../utils/notify'

const userStore = useUserStore()
const router = useRouter()
const route = useRoute()

function safeRedirectPath(): string {
  const r = route.query.redirect
  if (typeof r !== 'string' || !r.startsWith('/') || r.startsWith('//')) {
    return '/cases'
  }
  const pathOnly = r.split(/[?#]/)[0] ?? ''
  if (pathOnly === '/login' || pathOnly === '') {
    return '/cases'
  }
  return r
}

const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  username: 'admin',
  password: 'admin',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 64, message: '长度 2~64 字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 1, max: 128, message: '密码过长', trigger: 'blur' },
  ],
}

async function handleLogin() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    await userStore.login({ username: form.username.trim(), password: form.password })
    notifySuccess('登录成功')
    await router.push(safeRedirectPath())
  } catch (e) {
    notifyError(e instanceof Error ? e.message : '登录失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="hover">
      <template #header>
        <span class="login-title">检察调查辅助系统</span>
        <span class="login-sub">检察机关专用</span>
      </template>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="login-form">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" autocomplete="username" clearable />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" autocomplete="current-password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            class="login-btn"
            :loading="submitting"
            :disabled="submitting"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: linear-gradient(160deg, #1a365d 0%, #e8edf4 60%, var(--app-bg-layout) 100%);
}

.login-card {
  width: 100%;
  max-width: 420px;
  border-radius: var(--app-radius);
  border-color: var(--app-border);
}

.login-title {
  font-weight: 700;
  font-size: 22px;
  color: var(--app-primary);
}

.login-sub {
  display: block;
  margin-top: 4px;
  font-size: 13px;
  color: var(--app-text-secondary);
  font-weight: 400;
}

.login-tip {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--app-text-secondary);
  line-height: 1.5;
}

.login-tip code {
  font-size: 12px;
  padding: 2px 6px;
  background: var(--app-bg-layout);
  border-radius: 4px;
}

.login-form {
  margin-top: 4px;
}

.login-btn {
  width: 100%;
}
</style>
