<template>
  <section class="page" :data-module="meta.key">
    <header class="page-head">
      <div>
        <h2>{{ meta.name }}</h2>
        <p class="page-desc">{{ meta.desc }}</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" data-testid="open-create" type="button" @click="openCreate">
          登记{{ meta.entity }}
        </button>
        <button class="btn" data-testid="export" type="button" @click="exportRows">
          导出{{ meta.name }}清单
        </button>
        <button v-if="showHeritageChainButton" class="btn accent" data-testid="heritage-chain" type="button" @click="loadHeritageChain">
          传承链追溯
        </button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <p class="status-legend">
      <span v-for="item in statusSummary" :key="item.status" class="legend-item">
        {{ item.status }}：{{ item.count }}
      </span>
    </p>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :data-testid="`filter-${field}`" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" data-testid="query" type="submit">查询</button>
      <button class="btn ghost" data-testid="reset" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in meta.fields" :key="column">{{ column }}</th>
          <th v-if="showBatchColumn">申报批次标识</th>
          <th v-if="showBatchColumn">调查归档批号</th>
          <th>当前状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :data-testid="`row-${row.id}`" :data-status="String(row.status)">
          <td v-for="column in meta.fields" :key="column">{{ row[column] ?? '—' }}</td>
          <td v-if="showBatchColumn" :data-testid="`row-${row.id}-batch-id`">
            {{ row['申报批次标识'] || '—' }}
          </td>
          <td v-if="showBatchColumn" :data-testid="`row-${row.id}-archive-number`">
            {{ row['调查归档批号'] || '—' }}
          </td>
          <td>{{ row.status }}</td>
          <td class="row-actions">
            <button
              v-for="action in meta.actions"
              :key="action"
              class="link"
              type="button"
              :data-testid="`action-${row.id}-${action}`"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="meta.fields.length + 2 + (showBatchColumn ? 2 : 0)" class="empty-state">
            暂无{{ meta.name }}数据，可先登记{{ meta.entity }}
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 申报批次迁移面板 -->
    <aside v-if="isCraftCategory" class="batch-panel" data-testid="batch-panel">
      <div class="panel-head">
        <h3>申报批次迁移</h3>
        <div class="panel-head-actions">
          <span class="batch-summary" data-testid="batch-summary">
            已迁移 {{ batchSummary.migrated }} · 待补年度 {{ batchSummary.need_year }}
          </span>
          <button class="btn" data-testid="batch-migrate" type="button" @click="runMigration">执行迁移</button>
          <label class="switch-item">
            <input v-model="newUiEnabled" data-testid="batch-ui-toggle" type="checkbox" @change="toggleBatchUI" />
            新版批次界面
          </label>
        </div>
      </div>

      <div v-if="newUiEnabled" class="batch-content">
        <table class="data-table">
          <thead>
            <tr>
              <th>原编号</th><th>门类名称</th><th>申报批次</th><th>年度</th>
              <th>申报批次标识</th><th>调查归档批号</th><th>迁移状态</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="batch in batchSummary.items" :key="`batch-${batch.id}`" :data-testid="`batch-row-${batch.id}`">
              <td>{{ batch['登记编号'] }}</td>
              <td>{{ batch['门类名称'] }}</td>
              <td>{{ batch['申报批次'] }}</td>
              <td>{{ batch['年度'] || '—' }}</td>
              <td>{{ batch['申报批次标识'] || '—' }}</td>
              <td>{{ batch['调查归档批号'] || '—' }}</td>
              <td>{{ batch['迁移状态'] }}</td>
              <td>
                <button
                  v-if="batch['迁移状态'] !== '已迁移'"
                  class="link"
                  type="button"
                  :data-testid="`correct-year-${batch.id}`"
                  @click="openCorrection(batch.id)"
                >
                  补正年度
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="correctionTarget" class="correction-box" data-testid="correction-box">
          <strong>年份补正 · {{ correctionTarget }}</strong>
          <label class="create-field">
            <span>年度</span>
            <input v-model="correctionYear" data-testid="correction-year" placeholder="如 2024" />
          </label>
          <label class="create-field">
            <span>补正依据</span>
            <input v-model="correctionBasis" data-testid="correction-basis" placeholder="访谈记录、批复件等可核查依据" />
          </label>
          <div class="page-actions">
            <button class="btn" type="button" @click="correctionTarget = null">取消</button>
            <button class="btn primary" data-testid="submit-correction" type="button" @click="submitCorrection">
              提交补正
            </button>
          </div>
        </div>
      </div>
      <p v-else class="batch-disabled" data-testid="batch-ui-disabled">
        新版批次界面已停用；旧门类与旧批次号仍可按原编号查阅归档材料。
      </p>
    </aside>

    <!-- 调查归档面板 -->
    <aside v-if="isFieldSurvey" class="batch-panel" data-testid="survey-panel">
      <div class="panel-head">
        <h3>调查归档</h3>
      </div>
      <div class="archive-form">
        <label class="create-field">
          <span>调查记录 ID</span>
          <input v-model="archiveEntryId" data-testid="archive-entry-id" placeholder="如 4" />
        </label>
        <label class="create-field">
          <span>调查归档批号</span>
          <input v-model="archiveNumber" data-testid="archive-number" placeholder="如 DA-2024-001" />
        </label>
        <label class="create-field">
          <span>原编号（旧批次补档用）</span>
          <input v-model="archiveOriginalNumber" data-testid="archive-original-number" placeholder="如 CRAF-0004" />
        </label>
        <button class="btn primary" data-testid="submit-archive" type="button" @click="submitArchive">实际归档</button>
      </div>

      <div class="lookup-form">
        <label class="create-field">
          <span>按旧门类名称</span>
          <input v-model="lookupName" data-testid="lookup-name" placeholder="如 藤编" />
        </label>
        <label class="create-field">
          <span>按旧批次号</span>
          <input v-model="lookupBatch" data-testid="lookup-batch" placeholder="如 秋季申报" />
        </label>
        <label class="create-field">
          <span>按年度</span>
          <input v-model="lookupYear" data-testid="lookup-year" placeholder="如 2023" />
        </label>
        <label class="create-field">
          <span>按原编号</span>
          <input v-model="lookupOriginal" data-testid="lookup-original" placeholder="如 CRAF-0004" />
        </label>
        <label class="create-field">
          <span>按调查归档批号</span>
          <input v-model="lookupArchive" data-testid="lookup-archive" placeholder="如 DA-2024-001" />
        </label>
        <button class="btn" data-testid="lookup-archives" type="button" @click="searchArchives">查阅归档原件</button>
      </div>

      <p v-if="archiveMessage" data-testid="archive-message" class="batch-message">{{ archiveMessage }}</p>

      <div v-if="archiveGroups.length" class="archive-groups" data-testid="archive-groups">
        <div v-for="group in archiveGroups" :key="group.门类ID" class="archive-group" :data-batch="group.调查归档批号">
          <div class="chain-section">
            <span class="chain-label">{{ group.门类名称 }} · {{ group.申报批次 }} · {{ group.年度 || '年度待补' }}</span>
            <span class="chain-status">{{ group.申报批次标识 || '无新批次标识' }}</span>
            <span class="chain-status">{{ group.调查归档批号 || '无归档批号' }}</span>
            <span class="chain-status">原编号 {{ group.原编号 }}</span>
          </div>
          <ul class="archive-list">
            <li v-for="item in group.archives" :key="item.id" :data-testid="`archive-item-${item.id}`">
              {{ item['登记编号'] }} · {{ item['调查地点'] }} · {{ item['归档时间'] }}
            </li>
            <li v-if="!group.archives.length" class="empty-state">该批次暂无归档材料</li>
          </ul>
        </div>
      </div>
    </aside>

    <div v-if="showCreate" class="modal-backdrop" data-testid="create-modal">
      <form class="modal" @submit.prevent="submitCreate">
        <h3>登记{{ meta.entity }}</h3>
        <label v-for="field in meta.fields" :key="field" class="create-field">
          <span>{{ field }}</span>
          <input v-model="createValues[field]" :data-testid="`create-${field}`" required />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="showCreate = false">取消</button>
          <button class="btn primary" data-testid="submit-create" type="submit" :disabled="creating">
            {{ creating ? '提交中…' : '确认登记' }}
          </button>
        </div>
      </form>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条{{ meta.name }}记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-if="crossRefInfo" class="cross-ref-info">{{ crossRefInfo }}</span>
    </footer>

    <!-- 跨模块传承链面板 -->
    <aside v-if="showHeritagePanel" class="heritage-panel" data-testid="heritage-panel">
      <div class="panel-head">
        <h3>技艺传承链</h3>
        <button class="link" type="button" @click="showHeritagePanel = false">收起</button>
      </div>
      <div v-if="chainLoading" class="panel-loading">加载传承链中…</div>
      <div v-else-if="chainError" class="error-text">{{ chainError }}</div>
      <div v-else class="chain-display">
        <div class="chain-section" v-for="node in chainNodes" :key="node.id">
          <span class="chain-type-badge" :data-type="node.type">{{ node.type === 'craft_category' ? '门类' : node.type === 'artisan' ? '传承人' : node.type === 'apprentice' ? '学徒' : node.type === 'skill_card' ? '技艺' : node.type === 'creation_work' ? '作品' : node.type }}</span>
          <span class="chain-label">{{ node.label }}</span>
          <span v-if="node.data && node.data.status" class="chain-status" :data-status="node.data.status">{{ node.data.status }}</span>
        </div>
        <div v-if="!chainNodes.length" class="empty-state">暂无传承链数据，请先建立跨模块引用</div>
        <div class="chain-edges" v-if="chainEdges.length">
          <div class="edge-item" v-for="(edge, idx) in chainEdges" :key="idx">
            {{ edge.from }} → {{ edge.to }}: {{ edge.label }}
          </div>
        </div>
      </div>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  archiveSurvey,
  createEntry,
  correctBatchYear,
  downloadEntries,
  listEntries,
  loadBatchSummary,
  loadBatchUI,
  lookupArchives,
  migrateBatches,
  moduleMeta,
  runAction as applyAction,
  setBatchUI,
} from '@/api/backend-service'
import { fetchJson } from '@/api/client'
import type { BatchRow, EntryRow } from '@/data/types'

const props = defineProps<{ moduleKey: string }>()
const meta = moduleMeta(props.moduleKey)
const rows = ref<EntryRow[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = meta.fields.slice(0, 3)
const showCreate = ref(false)
const creating = ref(false)
const createValues = ref<Record<string, string>>({})

// 跨模块显示
const crossRefInfo = ref('')
const showHeritagePanel = ref(false)
const chainLoading = ref(false)
const chainError = ref('')
const chainNodes = ref<any[]>([])
const chainEdges = ref<any[]>([])

// 申报批次迁移
const isCraftCategory = computed(() => meta.key === 'craft_category')
const isFieldSurvey = computed(() => meta.key === 'field_survey')
const showBatchColumn = computed(() =>
  isCraftCategory.value && newUiEnabled.value,
)
const batchSummary = ref<{ total: number; migrated: number; need_year: number; items: BatchRow[] }>({
  total: 0,
  migrated: 0,
  need_year: 0,
  items: [],
})
const newUiEnabled = ref(true)
const correctionTarget = ref<number | null>(null)
const correctionYear = ref('')
const correctionBasis = ref('')

// 调查归档
const archiveEntryId = ref('')
const archiveNumber = ref('')
const archiveOriginalNumber = ref('')
const archiveMessage = ref('')
const archiveGroups = ref<any[]>([])
const lookupName = ref('')
const lookupBatch = ref('')
const lookupYear = ref('')
const lookupOriginal = ref('')
const lookupArchive = ref('')

const showHeritageChainButton = computed(() =>
  ['skill_card', 'artisan'].includes(meta.key)
)
const stats = computed(() => [
  { label: meta.metrics[0], value: total.value },
  { label: meta.metrics[1], value: rows.value.filter((row) => row.status === meta.statuses[1]).length },
  {
    label: meta.metrics[2],
    value: rows.value.filter((row) => row.status === meta.statuses[meta.statuses.length - 1]).length,
  },
])
const statusSummary = computed(() =>
  meta.statuses.map((status) => ({
    status,
    count: rows.value.filter((row) => String(row.status) === status).length,
  })),
)

function resetFilters() {
  filters.value = {}
  void reload()
}

async function exportRows() {
  errorMessage.value = ''
  try {
    await downloadEntries(meta.key, filters.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '导出失败'
  }
}

function openCreate() {
  createValues.value = Object.fromEntries(meta.fields.map((field) => [field, '']))
  errorMessage.value = ''
  showCreate.value = true
}

async function submitCreate() {
  creating.value = true
  errorMessage.value = ''
  try {
    const result = await createEntry(meta.key, createValues.value)
    if (!result.ok) throw new Error(result.message)
    showCreate.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登记失败'
  } finally {
    creating.value = false
  }
}

async function runAction(action: string, row: EntryRow) {
  errorMessage.value = ''
  try {
    const result = await applyAction(meta.key, Number(row.id), action)
    if (!result.ok) throw new Error(result.message)
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '操作失败'
  }
}

async function loadHeritageChain() {
  showHeritagePanel.value = !showHeritagePanel.value
  if (!showHeritagePanel.value) return
  chainLoading.value = true
  chainError.value = ''
  try {
    const params = new URLSearchParams()
    if (meta.key === 'skill_card' && rows.value.length > 0) {
      params.set('skill_card_id', String((rows.value[0] as any).id || 1))
    } else if (meta.key === 'artisan' && rows.value.length > 0) {
      params.set('artisan_id', String((rows.value[0] as any).id || 1))
    }
    const data = await fetchJson<any>(`/api/cross/heritage-chain?${params.toString()}`)
    const chain = data.chain || data
    chainNodes.value = chain.nodes || []
    chainEdges.value = chain.edges || []
  } catch (e: any) {
    chainError.value = e?.message || '传承链加载失败'
  } finally {
    chainLoading.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const payload = await listEntries(meta.key, filters.value)
    rows.value = payload.items
    total.value = payload.total
    // 显示跨模块引用提示
    loadCrossRefInfo()
    if (isCraftCategory.value) await loadBatchPanel()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '业务列表读取失败'
  }
}

async function loadBatchPanel() {
  try {
    const [summary, ui] = await Promise.all([loadBatchSummary(), loadBatchUI()])
    batchSummary.value = summary
    newUiEnabled.value = ui.new_ui_enabled
  } catch {
    // 后端不可达时保留原表格，不影响主列表。
  }
}

async function runMigration() {
  errorMessage.value = ''
  try {
    const result = await migrateBatches()
    if (!result.ok) throw new Error(result.message)
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '迁移失败'
  }
}

async function toggleBatchUI() {
  try {
    const result = await setBatchUI(newUiEnabled.value)
    newUiEnabled.value = result.new_ui_enabled
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '切换新版界面失败'
  }
}

function openCorrection(categoryId: number) {
  correctionTarget.value = categoryId
  correctionYear.value = ''
  correctionBasis.value = ''
}

async function submitCorrection() {
  if (correctionTarget.value === null) return
  errorMessage.value = ''
  try {
    const result = await correctBatchYear(
      correctionTarget.value,
      correctionYear.value,
      correctionBasis.value,
    )
    if (!result.ok) throw new Error(result.message)
    correctionTarget.value = null
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '年份补正失败'
  }
}

async function submitArchive() {
  archiveMessage.value = ''
  errorMessage.value = ''
  try {
    const result = await archiveSurvey(
      Number(archiveEntryId.value),
      archiveNumber.value,
      archiveOriginalNumber.value,
    )
    archiveMessage.value = result.message
    // 归档后直接按刚用到的批号重取原组证据。
    lookupArchive.value = String(result.entry['调查归档批号'] || archiveNumber.value || '')
    lookupOriginal.value = ''
    lookupName.value = ''
    lookupBatch.value = ''
    lookupYear.value = ''
    await reload()
    await searchArchives()
  } catch (error) {
    archiveMessage.value = error instanceof Error ? error.message : '归档失败'
  }
}

async function searchArchives() {
  errorMessage.value = ''
  try {
    const result = await lookupArchives({
      门类名称: lookupName.value,
      申报批次: lookupBatch.value,
      年度: lookupYear.value,
      原编号: lookupOriginal.value,
      调查归档批号: lookupArchive.value,
    })
    archiveGroups.value = result.batches || []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '归档查阅失败'
  }
}

async function loadCrossRefInfo() {
  try {
    const data = await fetchJson<any>('/api/cross/overview-refs')
    const links = data.cross_links
    if (!links) return
    const infoParts: string[] = []
    if (meta.key === 'artisan' && links.artisan_with_category !== undefined) infoParts.push(`${links.artisan_with_category} 位传承人已关联门类`)
    if (meta.key === 'apprentice' && links.apprentice_with_artisan !== undefined) infoParts.push(`${links.apprentice_with_artisan} 位学徒已关联师傅`)
    if (meta.key === 'skill_card' && links.skill_card_with_category !== undefined) infoParts.push(`${links.skill_card_with_category} 项技艺已归入门类`)
    if (meta.key === 'raw_material' && links.raw_material_with_skill !== undefined) infoParts.push(`${links.raw_material_with_skill} 批原料已关联技艺`)
    if (meta.key === 'tooling' && links.tooling_with_skill !== undefined) infoParts.push(`${links.tooling_with_skill} 件工具已关联技艺`)
    if (meta.key === 'creation_work' && links.creation_work_with_relations !== undefined) infoParts.push(`${links.creation_work_with_relations} 件作品已关联技艺和传承人`)
    if (meta.key === 'authentication' && links.authentication_with_work !== undefined) infoParts.push(`${links.authentication_with_work} 条认证已关联作品`)
    crossRefInfo.value = infoParts.length ? '跨模块引用: ' + infoParts.join('；') : ''
  } catch {
    crossRefInfo.value = ''
  }
}

onMounted(reload)
</script>
