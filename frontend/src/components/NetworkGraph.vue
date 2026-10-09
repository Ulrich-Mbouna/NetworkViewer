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
import { computed, markRaw, nextTick, ref, watch } from 'vue'
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

watch(
  () => {
    if (!props.network) return 'empty'
    const parts: string[] = [`v${props.network.meta.version}`]
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
            `${l.id}:${l.from_zone}>${l.to_zone}:${l.transport?.P_max ?? ''}:${l.transport?.P_flow ?? ''}`,
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
    class="uk-card uk-card-default overflow-hidden rounded-xl border border-slate-200 shadow-sm"
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
      </h3>
      <span class="flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span>{{ stats.zones }} zones</span>
        <span class="text-emerald-700">{{ stats.stations }} PS</span>
        <span class="text-emerald-700">{{ stats.gens }} gén.</span>
        <span class="text-orange-700">{{ stats.loads }} charges</span>
        <span>{{ stats.lines }} lignes</span>
      </span>
    </div>

    <div
      v-if="network"
      class="space-y-1.5 border-b border-slate-100 bg-slate-50 px-4 py-2 text-[11px] text-slate-600"
    >
      <div>
        <span class="font-semibold text-slate-700">Hiérarchie :</span>
        Zone → Power Station → Générateur · Charges dans la zone · Lignes entre zones
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

    <div v-else class="h-[560px] w-full bg-slate-50">
      <VueFlow
        :id="FLOW_ID"
        v-model:nodes="nodes"
        v-model:edges="edges"
        :node-types="nodeTypes"
        :default-viewport="{ zoom: 0.85, x: 0, y: 0 }"
        :min-zoom="0.25"
        :max-zoom="1.8"
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
