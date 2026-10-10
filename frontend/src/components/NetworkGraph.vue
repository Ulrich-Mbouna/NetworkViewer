<script setup lang="ts">
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import {
  VueFlow,
  MarkerType,
  useVueFlow,
  type Edge,
  type Node,
  type NodeTypesObject,
} from '@vue-flow/core'
import { computed, markRaw, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { ComponentType, NetworkModel } from '../api/types'
import ComponentGlyph from './ComponentGlyph.vue'
import ZoneNode from './ZoneNode.vue'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'

const props = defineProps<{
  network: NetworkModel | null
}>()

const FLOW_ID = 'triphase-network'
const COL_GAP = 300
const ROW_GAP = 280
const COLS = 3

const nodeTypes = { zone: markRaw(ZoneNode) } as NodeTypesObject
const nodes = ref<Node[]>([])
const edges = ref<Edge[]>([])
const seenIds = ref(new Set<string>())
const flashIds = ref(new Set<string>())
const rootEl = ref<HTMLElement | null>(null)
const isFullscreen = ref(false)

const { setNodes, setEdges, fitView } = useVueFlow(FLOW_ID)

const legend: { type: ComponentType; label: string }[] = [
  { type: 'generator', label: 'Générateur' },
  { type: 'source', label: 'Source' },
  { type: 'inverter', label: 'Onduleur' },
  { type: 'battery', label: 'Batterie' },
  { type: 'load', label: 'Charge' },
  { type: 'meter', label: 'Compteur' },
  { type: 'switch', label: 'Interrupteur' },
  { type: 'bus', label: 'Bus' },
]

const stats = computed(() => {
  if (!props.network) return { zones: 0, lines: 0, stations: 0, gens: 0, loads: 0 }
  let stations = 0
  let gens = 0
  let loads = 0
  for (const z of props.network.zones) {
    stations += (z.power_stations ?? []).length
    gens += (z.power_stations ?? []).reduce((n, ps) => n + ps.generators.length, 0)
    loads += (z.loads ?? []).length
  }
  return {
    zones: props.network.zones.length,
    lines: props.network.lines.length,
    stations,
    gens,
    loads,
  }
})

const totalCost = computed(() => {
  const t = props.network?.meta.total_line_cost
  if (t != null) return t
  if (!props.network) return null
  let sum = 0
  let any = false
  for (const ln of props.network.lines) {
    if (ln.cost?.cost != null) {
      sum += ln.cost.cost
      any = true
    }
  }
  return any ? sum : null
})

function collectEntityIds(network: NetworkModel): Set<string> {
  const ids = new Set<string>()
  for (const z of network.zones) {
    for (const ps of z.power_stations ?? []) {
      ids.add(`ps:${ps.id}`)
      for (const g of ps.generators) ids.add(`g:${g.id}`)
    }
    for (const l of z.loads ?? []) ids.add(`l:${l.id}`)
  }
  return ids
}

function buildNodes(network: NetworkModel, newIds: Set<string>): Node[] {
  return network.zones.map((z, i) => {
    const col = i % COLS
    const row = Math.floor(i / COLS)
    const powerStations = (z.power_stations ?? []).map((ps) => ({
      ...ps,
      isNew: newIds.has(`ps:${ps.id}`),
      generators: ps.generators.map((g) => ({
        ...g,
        isNew: newIds.has(`g:${g.id}`),
      })),
    }))
    const loads = (z.loads ?? []).map((l) => ({
      ...l,
      isNew: newIds.has(`l:${l.id}`),
    }))
    return {
      id: z.id,
      type: 'zone',
      position: { x: 24 + col * COL_GAP, y: 24 + row * ROW_GAP },
      data: {
        label: z.label || z.id,
        zoneId: z.id,
        powerStations,
        loads,
        balance: z.balance,
      },
      draggable: true,
    }
  })
}

function fmtEdgeW(v?: number | null): string {
  if (v == null || Number.isNaN(v)) return '—'
  if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)}k`
  return `${Math.round(v)}`
}

function fmtCost(v?: number | null, currency = 'CAD'): string {
  if (v == null || Number.isNaN(v)) return ''
  return `${v.toFixed(1)} ${currency}`
}

function buildEdges(network: NetworkModel): Edge[] {
  return network.lines.map((ln) => {
    const t = ln.transport
    const flow = t?.P_flow
    const max = t?.P_max
    const overloaded =
      max != null && flow != null && Math.abs(flow) > max + 1e-6
    const labelParts = [ln.id]
    if (flow != null || max != null) {
      labelParts.push(`${fmtEdgeW(flow)}/${fmtEdgeW(max)} W`)
    }
    if (ln.cost?.cost != null) {
      labelParts.push(fmtCost(ln.cost.cost, ln.cost.currency || 'CAD'))
    }
    return {
      id: ln.id,
      source: ln.from_zone,
      target: ln.to_zone,
      label: labelParts.join(' · '),
      type: 'smoothstep',
      animated: ln.kind === 'feeds',
      markerEnd: MarkerType.ArrowClosed,
      style: {
        stroke: overloaded ? '#dc2626' : '#2563eb',
        strokeWidth: overloaded ? 3 : 2.5,
      },
      labelStyle: {
        fontSize: 10,
        fill: overloaded ? '#b91c1c' : '#334155',
        fontWeight: 600,
      },
      labelBgStyle: { fill: '#fff', fillOpacity: 0.95 },
      labelBgPadding: [4, 6] as [number, number],
    }
  })
}

async function syncGraph(network: NetworkModel | null) {
  if (!network) {
    nodes.value = []
    edges.value = []
    setNodes([])
    setEdges([])
    return
  }

  const currentIds = collectEntityIds(network)
  const newIds = new Set([...currentIds].filter((id) => !seenIds.value.has(id)))
  flashIds.value = newIds

  const nextNodes = buildNodes(network, newIds)
  const nextEdges = buildEdges(network)
  nodes.value = nextNodes
  edges.value = nextEdges
  setNodes(nextNodes)
  setEdges(nextEdges)
  seenIds.value = currentIds

  await nextTick()
  try {
    await fitView({ padding: 0.12, duration: 320 })
  } catch {
    /* ignore */
  }

  if (newIds.size) {
    window.setTimeout(() => {
      flashIds.value = new Set()
      if (props.network) {
        const refreshed = buildNodes(props.network, new Set())
        nodes.value = refreshed
        setNodes(refreshed)
      }
    }, 1000)
  }
}

async function toggleFullscreen() {
  const el = rootEl.value
  if (!el) return
  try {
    if (!document.fullscreenElement) {
      await el.requestFullscreen()
    } else {
      await document.exitFullscreen()
    }
  } catch {
    /* ignore denied */
  }
}

function onFullscreenChange() {
  isFullscreen.value = document.fullscreenElement === rootEl.value
  void nextTick(async () => {
    try {
      await fitView({ padding: 0.1, duration: 280 })
    } catch {
      /* ignore */
    }
  })
}

onMounted(() => {
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onUnmounted(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})

watch(
  () => {
    if (!props.network) return 'empty'
    const parts: string[] = [
      `v${props.network.meta.version}`,
      `tc:${props.network.meta.total_line_cost ?? ''}`,
    ]
    for (const z of props.network.zones) {
      parts.push(z.id)
      for (const ps of z.power_stations ?? []) {
        parts.push(
          `ps:${ps.id}:${ps.generators
            .map(
              (g) =>
                `${g.id}:${g.production?.P_eff ?? ''}:${g.production?.P_min ?? ''}:${g.production?.P_max ?? ''}`,
            )
            .join('+')}`,
        )
      }
      parts.push(
        `L:${(z.loads ?? []).map((l) => `${l.id}:${l.demand?.P_demand ?? ''}`).join('+')}`,
      )
      const b = z.balance
      if (b) {
        parts.push(
          `B:${b.P_production}:${b.P_demand}:${b.P_surplus}:${b.P_in}:${b.P_out}`,
        )
      }
    }
    parts.push(
      props.network.lines
        .map(
          (l) =>
            `${l.id}:${l.from_zone}>${l.to_zone}:${l.transport?.P_max ?? ''}:${l.transport?.P_flow ?? ''}:${l.cost?.c0 ?? ''}:${l.cost?.c1 ?? ''}:${l.cost?.c2 ?? ''}:${l.cost?.cost ?? ''}`,
        )
        .join(','),
    )
    return parts.join('|')
  },
  () => {
    void syncGraph(props.network)
  },
  { immediate: true },
)
</script>

<template>
  <div
    ref="rootEl"
    class="graph-shell uk-card uk-card-default overflow-hidden rounded-xl border border-slate-200 shadow-sm"
    :class="{ 'graph-shell--fs': isFullscreen }"
  >
    <div
      class="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-3"
    >
      <h3 class="m-0 flex items-center gap-2 text-lg font-semibold">
        <span
          class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700"
          uk-icon="icon: world"
        ></span>
        Graphe du réseau
        <span v-if="network" class="uk-badge bg-sky-500">{{ network.meta.name }}</span>
        <span v-if="network" class="uk-label uk-label-success text-xs">
          v{{ network.meta.version }}
        </span>
        <span
          v-if="totalCost != null"
          class="uk-label uk-label-warning text-xs"
          title="Somme des coûts de transport"
        >
          Coût total {{ totalCost.toFixed(1) }} CAD
        </span>
      </h3>
      <div class="flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span>{{ stats.zones }} zones</span>
        <span class="text-emerald-700">{{ stats.stations }} PS</span>
        <span class="text-emerald-700">{{ stats.gens }} gén.</span>
        <span class="text-orange-700">{{ stats.loads }} charges</span>
        <span>{{ stats.lines }} lignes</span>
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
          :title="isFullscreen ? 'Quitter le plein écran (Échap)' : 'Plein écran'"
          @click="toggleFullscreen"
        >
          <span
            :uk-icon="isFullscreen ? 'icon: shrink; ratio: 0.85' : 'icon: expand; ratio: 0.85'"
          ></span>
          {{ isFullscreen ? 'Réduire' : 'Plein écran' }}
        </button>
      </div>
    </div>

    <div
      v-if="network && !isFullscreen"
      class="space-y-1.5 border-b border-slate-100 bg-slate-50 px-4 py-2 text-[11px] text-slate-600"
    >
      <div>
        <span class="font-semibold text-slate-700">Hiérarchie :</span>
        Zone → Power Station → Générateur · Charges dans la zone · Lignes entre zones
      </div>
      <div>
        <span class="font-semibold text-slate-700">Coût ligne :</span>
        cost(|P|) = c0 + c1·|P| + c2·P² — affiché sur chaque arête
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <span class="font-semibold text-slate-700">Légende :</span>
        <span
          v-for="item in legend"
          :key="item.type"
          class="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-1.5 py-0.5"
        >
          <ComponentGlyph :type="item.type" :size="20" />
          <span>{{ item.label }}</span>
        </span>
      </div>
    </div>

    <div v-if="!network" class="px-4 py-12 text-center text-sm text-slate-400">
      Aucun réseau chargé
    </div>

    <div v-else class="graph-canvas w-full bg-slate-50">
      <VueFlow
        :id="FLOW_ID"
        v-model:nodes="nodes"
        v-model:edges="edges"
        :node-types="nodeTypes"
        :default-viewport="{ zoom: 0.85, x: 0, y: 0 }"
        :min-zoom="0.15"
        :max-zoom="2.2"
        fit-view-on-init
        nodes-draggable
      >
        <Background :gap="18" :size="1" color="#cbd5e1" />
        <Controls :show-interactive="false" position="bottom-left" />
      </VueFlow>
    </div>
  </div>
</template>

<style>
.graph-canvas {
  height: 560px;
}

.graph-shell--fs {
  border-radius: 0 !important;
  background: #f8fafc;
}

.graph-shell--fs .graph-canvas {
  height: calc(100vh - 64px);
}

.comp-chip--new {
  animation: comp-pop 0.55s cubic-bezier(0.22, 1.2, 0.36, 1) both;
}
@keyframes comp-pop {
  0% {
    opacity: 0;
    transform: scale(0.4) translateY(8px);
  }
  60% {
    opacity: 1;
    transform: scale(1.08);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
