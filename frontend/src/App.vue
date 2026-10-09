<script setup lang="ts">
import { onMounted, ref } from 'vue'
import * as api from './api/client'
import type { NetworkModel, Suggestion, ValidationReport } from './api/types'
import ChatPanel from './components/ChatPanel.vue'
import DiagnosticsPanel from './components/DiagnosticsPanel.vue'
import ImportPanel from './components/ImportPanel.vue'
import NetworkGraph from './components/NetworkGraph.vue'
import SessionLoader from './components/SessionLoader.vue'
import { useProcessing } from './composables/useProcessing'
import { notifyError, notifySuccess, notify } from './utils/notify'

const network = ref<NetworkModel | null>(null)
const validation = ref<ValidationReport | null>(null)
const suggestions = ref<Suggestion[]>([])
const applyingId = ref<string | null>(null)

const {
  run: runNav,
  visible: navVisible,
  label: navLabel,
  steps: navSteps,
  running: navRunning,
  error: navError,
} = useProcessing('nav')

const { run: runDiagnostics } = useProcessing('diagnostics')

async function refresh() {
  try {
    await runNav('Chargement', ['Réseau', 'Validation', 'Suggestions'], async (next) => {
      network.value = await api.getNetwork()
      next()
      validation.value = await api.validateNetwork()
      next()
      suggestions.value = await api.getSuggestions()
      next()
    })
  } catch (e) {
    notifyError(e instanceof Error ? e.message : String(e))
  }
}

function onUpdated(
  n: NetworkModel,
  v: ValidationReport | null,
  s?: Suggestion[],
) {
  let stations = 0
  let gens = 0
  let loads = 0
  for (const z of n.zones) {
    stations += (z.power_stations ?? []).length
    gens += (z.power_stations ?? []).reduce((a, ps) => a + ps.generators.length, 0)
    loads += (z.loads ?? []).length
  }
  network.value = structuredClone(n)
  validation.value = v ? structuredClone(v) : null
  if (s) suggestions.value = structuredClone(s)
  else void api.getSuggestions().then((list) => (suggestions.value = list))
  notifySuccess(
    `Réseau sync (v${n.meta.version}) — ${n.zones.length} zones · ${stations} PS · ${gens} gén. · ${loads} charges · ${n.lines.length} lignes`,
  )
}

async function onExport() {
  try {
    await runNav('Export Excalidraw', ['Génération', 'Téléchargement'], async (next) => {
      next()
      await api.downloadExcalidraw()
      next()
    })
    notify('Export .excalidraw téléchargé', 'primary')
  } catch (e) {
    notifyError(e instanceof Error ? e.message : String(e))
  }
}

async function onValidate() {
  try {
    await runNav('Validation', ['Analyse', 'Suggestions'], async (next) => {
      validation.value = await api.validateNetwork()
      next()
      suggestions.value = await api.getSuggestions()
      next()
    })
  } catch (e) {
    notifyError(e instanceof Error ? e.message : String(e))
  }
}

async function onApplySuggestion(s: Suggestion) {
  applyingId.value = s.id
  try {
    await runDiagnostics(
      `Suggestion: ${s.title}`,
      ['Application', 'Sync UI'],
      async (next) => {
        const res = await api.applyOps(s.operations)
        next()
        // Reuse the same path as chat/import so the graph remounts
        onUpdated(res.network, res.validation, res.suggestions)
        next()
      },
    )
  } catch (e) {
    notifyError(e instanceof Error ? e.message : String(e))
  } finally {
    applyingId.value = null
  }
}

onMounted(refresh)
</script>

<template>
  <div class="min-h-screen bg-slate-100">
    <nav
      class="uk-navbar-container border-b border-slate-200 bg-white px-4 shadow-sm"
      uk-navbar
    >
      <div class="uk-navbar-left">
        <a
          class="uk-navbar-item uk-logo flex items-center gap-2 text-xl font-bold text-sky-700"
          href="#"
        >
          <span
            class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-sky-200 bg-sky-50"
            uk-icon="icon: bolt"
          ></span>
          TriPhase
        </a>
        <span class="hidden text-sm text-slate-500 sm:inline">
          Modélisation réseau · Gemma 4
        </span>
      </div>
      <div class="uk-navbar-right flex flex-wrap items-center gap-2 py-2">
        <button
          class="uk-button uk-button-default uk-button-small rounded-lg border border-slate-300"
          :disabled="navRunning"
          @click="refresh"
        >
          <span v-if="navRunning" uk-spinner="ratio: 0.5"></span>
          <span v-else uk-icon="icon: refresh"></span>
          Rafraîchir
        </button>
        <button
          class="uk-button uk-button-default uk-button-small rounded-lg border border-slate-300"
          :disabled="navRunning"
          @click="onValidate"
        >
          <span uk-icon="icon: check"></span>
          Valider
        </button>
        <button
          class="uk-button uk-button-primary uk-button-small rounded-lg border border-sky-600"
          :disabled="navRunning"
          @click="onExport"
        >
          <span uk-icon="icon: download"></span>
          Excalidraw
        </button>
      </div>
    </nav>

    <main class="mx-auto max-w-7xl space-y-4 p-4 md:p-6">
      <div
        v-if="navVisible"
        class="rounded-xl border border-slate-200 bg-white px-4 pb-1 pt-1 shadow-sm"
      >
        <SessionLoader
          :visible="navVisible"
          :label="navLabel"
          :steps="navSteps"
          :running="navRunning"
          :error="navError"
        />
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <ImportPanel @updated="onUpdated" @error="notifyError" />
        <ChatPanel @updated="onUpdated" @error="notifyError" />
      </div>

      <div class="grid gap-4 lg:grid-cols-3">
        <div class="lg:col-span-2">
          <NetworkGraph :network="network" />
        </div>
        <DiagnosticsPanel
          :validation="validation"
          :suggestions="suggestions"
          :applying-id="applyingId"
          @apply="onApplySuggestion"
        />
      </div>
    </main>
  </div>
</template>
