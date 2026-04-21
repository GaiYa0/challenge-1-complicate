import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      dts: 'src/types/auto-imports.d.ts',
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'src/types/auto-components.d.ts',
    }),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        proxyTimeout: 120_000,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    target: 'es2020',
    sourcemap: false,
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks: (id: string) => {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('/@antv/g6/') || id.includes('/@antv/layout')) return 'g6-vendor'
          if (id.includes('/echarts/') || id.includes('/zrender/')) return 'echarts-vendor'
          if (id.includes('/element-plus/') || id.includes('/@element-plus/')) return 'el-plus-vendor'
          if (id.includes('/vue-router/') || id.includes('/@vue/') || id.includes('/vue/dist/') || id.includes('/pinia/')) return 'vue-vendor'
          if (id.includes('/axios/')) return 'net-vendor'
          if (id.includes('/@tanstack/')) return 'table-vendor'
          return 'deps-vendor'
        },
      },
    },
  },
  esbuild: {
    drop: process.env.NODE_ENV === 'production' ? ['console', 'debugger'] : [],
  },
})
