import http from './request'

export interface ModelTrainResult {
  model_name: string
  model_version: string
  feature_version: string
  eval_accuracy: number
  eval_precision: number
  eval_recall: number
  registry_id: number
  object_path: string
  status: string
}

export interface CeleryTaskSubmitData {
  task_id: string
  queue: string
  state: string
}

export interface ModelPredictData {
  prediction: number
  model_name?: string | null
  model_version?: string | null
  registry_status?: string | null
}

export interface ModelRegistryOut {
  id: number
  model_name: string
  version: string
  feature_version: string
  object_path: string
  eval_accuracy: number
  eval_precision: number
  eval_recall: number
  traffic_percent: number
  status: string
  created_at: string | null
}

export interface ModelVersionIn {
  model_name?: string
  version: string
}

export interface ModelCanaryIn {
  model_name?: string
  version: string
  traffic_percent: number
}

export interface TrainQuery {
  model_name?: string
  feature_version?: string
  /** 管理员：使用全租户该 feature_version 的特征训练 */
  use_all_features?: boolean
}

/** POST /model/train（同步，可能较慢） */
export function trainModelSync(params: TrainQuery) {
  return http.post('/model/train', undefined, {
    params: {
      model_name: params.model_name ?? 'default',
      feature_version: params.feature_version ?? 'v1',
      use_all_features: params.use_all_features ?? false,
    },
    timeout: 120_000,
  }) as Promise<ModelTrainResult>
}

/** POST /model/train-async */
export function trainModelAsync(params: TrainQuery) {
  return http.post('/model/train-async', undefined, {
    params: {
      model_name: params.model_name ?? 'default',
      feature_version: params.feature_version ?? 'v1',
      use_all_features: params.use_all_features ?? false,
    },
    timeout: 30_000,
  }) as Promise<CeleryTaskSubmitData>
}

/** GET /model/predict/{filename}；`silent` 时由调用方自行处理错误，不弹全局提示 */
export function predictSync(filename: string, model_name = 'default', silent = true) {
  return http.get(`/model/predict/${encodeURIComponent(filename)}`, {
    params: { model_name },
    timeout: 60_000,
    silentError: silent,
  }) as Promise<ModelPredictData>
}

/** POST /model/predict-async/{filename} */
export function predictAsync(filename: string, model_name = 'default') {
  return http.post(`/model/predict-async/${encodeURIComponent(filename)}`, undefined, {
    params: { model_name },
  }) as Promise<CeleryTaskSubmitData>
}

/** GET /model/registry */
export function listModelRegistry(model_name = 'default') {
  return http.get('/model/registry', { params: { model_name } }) as Promise<ModelRegistryOut[]>
}

/** POST /model/registry/activate（admin） */
export function activateRegistryVersion(body: ModelVersionIn) {
  return http.post('/model/registry/activate', {
    model_name: body.model_name ?? 'default',
    version: body.version,
  })
}

/** POST /model/registry/canary（admin） */
export function setRegistryCanary(body: ModelCanaryIn) {
  return http.post('/model/registry/canary', {
    model_name: body.model_name ?? 'default',
    version: body.version,
    traffic_percent: body.traffic_percent,
  })
}

/** POST /model/registry/promote-canary（admin） */
export function promoteCanary(model_name = 'default') {
  return http.post('/model/registry/promote-canary', undefined, { params: { model_name } })
}

/** POST /model/registry/rollback（admin） */
export function rollbackRegistry(body: ModelVersionIn) {
  return http.post('/model/registry/rollback', {
    model_name: body.model_name ?? 'default',
    version: body.version,
  })
}
