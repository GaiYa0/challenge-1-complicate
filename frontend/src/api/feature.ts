import http from './request'
import type { TaskEnqueueData } from './task'

export interface FeatureMapData {
  entity_id: number
  version: string
  features: Record<string, unknown>
}

/** POST /feature/{filename} → 投递特征提取 Celery 任务 */
export function extractFeatureJob(filename: string) {
  return http.post(`/feature/${encodeURIComponent(filename)}`) as Promise<TaskEnqueueData>
}

/** GET /features/entity/{entity_id}?version= — 优先 Redis，否则 DB */
export function getFeatureEntityMap(entityId: number, version = 'v1') {
  return http.get(`/features/entity/${entityId}`, {
    params: { version },
  }) as Promise<FeatureMapData>
}
