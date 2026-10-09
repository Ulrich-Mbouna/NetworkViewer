import { computed, reactive } from 'vue'

export type ProcessStepStatus = 'pending' | 'active' | 'done' | 'error'

export interface ProcessStep {
  id: string
  label: string
  status: ProcessStepStatus
}

interface ScopeState {
  steps: ProcessStep[]
  running: boolean
  label: string
  error: string | null
}

const scopes = reactive<Record<string, ScopeState>>({})

function emptyState(): ScopeState {
  return { steps: [], running: false, label: '', error: null }
}

function getScope(id: string): ScopeState {
  if (!scopes[id]) scopes[id] = emptyState()
  return scopes[id]
}

/** Progress scoped to a UI section (import, chat, nav, diagnostics…). */
export function useProcessing(scopeId = 'global') {
  const state = computed(() => getScope(scopeId))
  const visible = computed(
    () => state.value.running || state.value.steps.length > 0,
  )

  function start(title: string, stepLabels: string[]) {
    const s = getScope(scopeId)
    s.label = title
    s.error = null
    s.running = true
    s.steps = stepLabels.map((l, i) => ({
      id: `s${i}`,
      label: l,
      status: (i === 0 ? 'active' : 'pending') as ProcessStepStatus,
    }))
  }

  function advance() {
    const s = getScope(scopeId)
    const idx = s.steps.findIndex((st) => st.status === 'active')
    if (idx < 0) return
    s.steps[idx] = { ...s.steps[idx], status: 'done' }
    if (idx + 1 < s.steps.length) {
      s.steps[idx + 1] = { ...s.steps[idx + 1], status: 'active' }
    }
  }

  function fail(message: string) {
    const s = getScope(scopeId)
    s.error = message
    s.running = false
    const idx = s.steps.findIndex((st) => st.status === 'active')
    if (idx >= 0) s.steps[idx] = { ...s.steps[idx], status: 'error' }
  }

  function finish() {
    const s = getScope(scopeId)
    s.steps = s.steps.map((st) =>
      st.status === 'pending' || st.status === 'active'
        ? { ...st, status: 'done' as const }
        : st,
    )
    s.running = false
    window.setTimeout(() => {
      const cur = getScope(scopeId)
      if (!cur.running) {
        cur.steps = []
        cur.label = ''
        cur.error = null
      }
    }, 1400)
  }

  async function run<T>(
    title: string,
    stepLabels: string[],
    work: (advanceStep: () => void) => Promise<T>,
  ): Promise<T> {
    start(title, stepLabels)
    try {
      const result = await work(() => advance())
      finish()
      return result
    } catch (e) {
      fail(e instanceof Error ? e.message : String(e))
      throw e
    }
  }

  return {
    steps: computed(() => state.value.steps),
    running: computed(() => state.value.running),
    label: computed(() => state.value.label),
    error: computed(() => state.value.error),
    visible,
    start,
    advance,
    fail,
    finish,
    run,
  }
}
