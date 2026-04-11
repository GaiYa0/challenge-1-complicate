<script setup lang="ts">
import { useVirtualizer } from '@tanstack/vue-virtual'
import { computed, ref } from 'vue'

export interface VirtualTableRow {
  id: number
  name: string
  metric: number
  status: string
}

const props = withDefaults(
  defineProps<{
    items: VirtualTableRow[]
    rowHeight?: number
    /** 可视区域高度（px） */
    viewportHeight?: number
  }>(),
  {
    rowHeight: 36,
    viewportHeight: 360,
  },
)

const parentRef = ref<HTMLDivElement | null>(null)

const virtualizer = useVirtualizer(
  computed(() => ({
    count: props.items.length,
    getScrollElement: () => parentRef.value,
    estimateSize: () => props.rowHeight,
    overscan: 8,
  })),
)
</script>

<template>
  <div class="vtable-wrap">
    <div class="thead">
      <span class="cell id">ID</span>
      <span class="cell name">名称</span>
      <span class="cell metric">指标</span>
      <span class="cell status">状态</span>
    </div>
    <div
      ref="parentRef"
      class="tbody-scroll"
      :style="{ height: `${props.viewportHeight}px` }"
      role="list"
    >
      <div class="tbody-inner" :style="{ height: `${virtualizer.getTotalSize()}px` }">
        <div
          v-for="row in virtualizer.getVirtualItems()"
          :key="items[row.index]?.id ?? row.index"
          class="trow"
          role="listitem"
          :style="{
            height: `${row.size}px`,
            transform: `translateY(${row.start}px)`,
          }"
        >
          <span class="cell id">{{ items[row.index]?.id }}</span>
          <span class="cell name">{{ items[row.index]?.name }}</span>
          <span class="cell metric">{{ items[row.index]?.metric }}</span>
          <span class="cell status">{{ items[row.index]?.status }}</span>
        </div>
      </div>
    </div>
    <p class="meta">共 {{ items.length }} 行 · 仅挂载可视区附近行节点</p>
  </div>
</template>

<style scoped>
.vtable-wrap {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.thead {
  display: grid;
  grid-template-columns: 64px 1fr 80px 88px;
  gap: 0;
  padding: 8px 12px;
  font-weight: 600;
  font-size: 13px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}

.tbody-scroll {
  overflow: auto;
  position: relative;
}

.tbody-inner {
  position: relative;
  width: 100%;
}

.trow {
  position: absolute;
  left: 0;
  right: 0;
  display: grid;
  grid-template-columns: 64px 1fr 80px 88px;
  align-items: center;
  padding: 0 12px;
  font-size: 14px;
  border-bottom: 1px solid #f3f4f6;
  box-sizing: border-box;
}

.cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta {
  padding: 6px 12px;
  font-size: 12px;
  color: #6b7280;
  margin: 0;
  border-top: 1px solid #e5e7eb;
}
</style>
