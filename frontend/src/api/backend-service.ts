import { fetchJson, request } from './client'
import { moduleMeta } from '@/data/modules'
import type { ActionResult, BatchRow, EntryRow, OverviewResult, PageResult } from '@/data/types'

export { moduleMeta }

export async function listEntries(
  key: string,
  filters: Record<string, string> = {},
): Promise<PageResult> {
  const query = new URLSearchParams(filters).toString()
  const response = await request(`/api/${key}?${query}`)
  if (!response.ok) throw new Error('业务数据读取失败')
  return await response.json()
}

export async function createEntry(
  key: string,
  values: Record<string, string>,
): Promise<ActionResult> {
  const response = await request(`/api/${key}`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  return await response.json()
}

export async function runAction(
  key: string,
  id: number,
  action: string,
): Promise<ActionResult> {
  const response = await request(`/api/${key}/${id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  })
  return await response.json()
}

export async function downloadEntries(
  key: string,
  filters: Record<string, string> = {},
): Promise<void> {
  const query = new URLSearchParams(filters).toString()
  const response = await request(`/api/${key}/export?${query}`)
  if (!response.ok) throw new Error('业务数据导出失败')
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${key}.csv`
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export async function loadOverview(): Promise<OverviewResult> {
  const response = await request('/api/overview')
  if (!response.ok) throw new Error('运营概览读取失败')
  return await response.json()
}

// ── 申报批次迁移与调查归档 ─────────────────────────────────────

function query(params: Record<string, string>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value) search.set(key, value)
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

export async function loadBatchSummary(): Promise<{ total: number; migrated: number; need_year: number; items: BatchRow[] }> {
  return await fetchJson('/api/batch-category/batches')
}

export async function migrateBatches(): Promise<{ ok: boolean; message: string }> {
  const response = await request('/api/batch-category/migrate', { method: 'POST' })
  return await response.json()
}

export async function correctBatchYear(
  categoryId: number,
  year: string,
  basis: string,
): Promise<{ ok: boolean; message: string; entry?: BatchRow }> {
  const response = await request(`/api/batch-category/${categoryId}/correct-year`, {
    method: 'POST',
    body: JSON.stringify({ 年度: year, 依据: basis }),
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail || '年份补正失败')
  return data
}

export async function lookupBatches(params: Record<string, string>): Promise<{ items: BatchRow[]; total: number }> {
  return await fetchJson(`/api/batch-category/lookup${query(params)}`)
}

export async function loadBatchUI(): Promise<{ new_ui_enabled: boolean }> {
  return await fetchJson('/api/batch-ui')
}

export async function setBatchUI(enabled: boolean): Promise<{ ok: boolean; new_ui_enabled: boolean; message: string }> {
  const response = await request('/api/batch-ui', {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
  return await response.json()
}

export async function archiveSurvey(
  entryId: number,
  archiveNumber: string,
  originalNumber: string,
): Promise<{ ok: boolean; message: string; entry: EntryRow }> {
  const response = await request(`/api/field_survey/${entryId}/archive`, {
    method: 'POST',
    body: JSON.stringify({ 调查归档批号: archiveNumber, 原编号: originalNumber }),
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail || '归档失败')
  return data
}

export async function loadSurveyLocators(entryId: number): Promise<any> {
  return await fetchJson(`/api/field_survey/${entryId}/locators`)
}

export async function lookupArchives(params: Record<string, string>): Promise<any> {
  return await fetchJson(`/api/field_survey/archive-lookup${query(params)}`)
}
