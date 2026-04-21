<script setup lang="ts">
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { useThemeStore } from './store/modules/theme.store'
// 引用一次以确保主题 store 在根组件作用域内被持有（触发响应式）。
useThemeStore()
</script>

<template>
  <el-config-provider :locale="zhCn" size="default">
    <router-view />
  </el-config-provider>
</template>
