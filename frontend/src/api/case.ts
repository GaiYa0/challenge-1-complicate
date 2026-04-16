import request from './request'

export interface CaseOut {
  id: number
  name: string
  case_number: string | null
  note: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface CaseCreate {
  name: string
  case_number?: string
  note?: string
}

export interface CaseUpdate {
  name?: string
  case_number?: string
  note?: string
  status?: 'active' | 'completed'
}

export function listCases() {
  return request.get<CaseOut[]>('/case')
}

export function createCase(body: CaseCreate) {
  return request.post<CaseOut>('/case', body)
}

export function getCase(id: number) {
  return request.get<CaseOut>(`/case/${id}`)
}

export function updateCase(id: number, body: CaseUpdate) {
  return request.put<CaseOut>(`/case/${id}`, body)
}

export function deleteCase(id: number) {
  return request.delete<null>(`/case/${id}`)
}
