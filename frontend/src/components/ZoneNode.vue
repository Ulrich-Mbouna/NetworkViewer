<script setup lang="ts">
import { Handle, Position, type NodeProps } from '@vue-flow/core'
import type { NetworkComponent, PowerStation } from '../api/types'
import ComponentGlyph from './ComponentGlyph.vue'

export type ZoneNodeData = {
  label: string
  zoneId: string
  powerStations: (PowerStation & {
    isNew?: boolean
    generators: (NetworkComponent & { isNew?: boolean })[]
  })[]
  loads: (NetworkComponent & { isNew?: boolean })[]
}

defineProps<NodeProps<ZoneNodeData>>()

const typeLabel: Record<string, string> = {
  generator: 'Gén.',
  source: 'Source',
  inverter: 'Ond.',
  battery: 'Batt.',
  load: 'Charge',
  meter: 'Cpt.',
  switch: 'Inter.',
  bus: 'Bus',
}
</script>

<template>
  <div
    class="zone-node min-w-[240px] max-w-[300px] rounded-xl border-2 border-sky-500 bg-gradient-to-b from-sky-50 to-white px-2.5 py-2 shadow-md"
  >
    <Handle type="target" :position="Position.Left" class="!bg-sky-600" />
    <Handle type="source" :position="Position.Right" class="!bg-sky-600" />

    <!-- Zone -->
    <div class="mb-2 flex items-center gap-2 border-b border-sky-200 pb-1.5">
      <div
        class="flex h-8 w-8 items-center justify-center rounded-lg border border-sky-300 bg-sky-100 text-sky-800"
        title="Zone"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
          <rect
            x="3"
            y="3"
            width="18"
            height="18"
            rx="3"
            stroke="#0369a1"
            stroke-width="2"
          />
          <path
            d="M3 9h18M9 9v12"
            stroke="#0369a1"
            stroke-width="1.6"
          />
        </svg>
      </div>
      <div class="min-w-0 flex-1">
        <div class="text-[10px] font-semibold uppercase tracking-wide text-sky-600">
          Zone
        </div>
        <div class="truncate text-sm font-bold text-sky-950">{{ data.label }}</div>
        <div class="font-mono text-[10px] text-sky-700/70">{{ data.zoneId }}</div>
      </div>
      <div class="text-right text-[10px] leading-tight text-slate-500">
        <div>{{ data.powerStations.length }} PS</div>
        <div>{{ data.loads.length }} ch.</div>
      </div>
    </div>

    <!-- Power stations -->
    <div v-if="data.powerStations.length" class="mb-2 space-y-1.5">
      <div
        v-for="(ps, psi) in data.powerStations"
        :key="ps.id"
        class="rounded-lg border-2 border-emerald-400 bg-emerald-50/90 p-1.5"
        :class="ps.isNew ? 'comp-chip--new' : ''"
        :style="ps.isNew ? { animationDelay: `${psi * 60}ms` } : undefined"
      >
        <div class="mb-1.5 flex items-center gap-1.5">
          <div
            class="flex h-7 w-7 items-center justify-center rounded-md border border-emerald-400 bg-white"
            title="Power Station"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path
                d="M4 20V10l4-3 4 2 4-3 4 3v11H4z"
                stroke="#15803d"
                stroke-width="1.8"
                stroke-linejoin="round"
              />
              <path d="M9 20v-6h6v6" stroke="#15803d" stroke-width="1.8" />
              <path
                d="M12 3v3M8 5l1.5 2M16 5l-1.5 2"
                stroke="#15803d"
                stroke-width="1.5"
                stroke-linecap="round"
              />
            </svg>
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-[9px] font-semibold uppercase text-emerald-700">
              Power Station
            </div>
            <div class="truncate text-[11px] font-bold text-emerald-950">
              {{ ps.label || ps.id }}
            </div>
          </div>
          <span class="font-mono text-[9px] text-emerald-700/70">{{ ps.id }}</span>
        </div>

        <div class="flex flex-wrap gap-1.5">
          <div
            v-for="(g, gi) in ps.generators"
            :key="g.id"
            class="comp-chip flex items-center gap-1 rounded-lg border border-emerald-200 bg-white px-1 py-0.5 pr-1.5 shadow-sm"
            :class="g.isNew ? 'comp-chip--new' : ''"
            :style="g.isNew ? { animationDelay: `${(psi + gi) * 70}ms` } : undefined"
          >
            <ComponentGlyph :type="g.type" :size="26" :title="g.type" />
            <div class="min-w-0 leading-tight">
              <div class="truncate font-mono text-[10px] font-semibold text-slate-800">
                {{ g.label || g.id }}
              </div>
              <div class="text-[9px] text-slate-500">
                {{ typeLabel[g.type] || g.type }}
              </div>
            </div>
          </div>
          <div
            v-if="!ps.generators.length"
            class="text-[9px] italic text-emerald-700/60"
          >
            (sans générateur)
          </div>
        </div>
      </div>
    </div>
    <div v-else class="mb-2 text-[10px] italic text-slate-400">
      Aucune power station
    </div>

    <!-- Loads / other zone devices -->
    <div class="border-t border-dashed border-orange-200 pt-1.5">
      <div class="mb-1.5 text-[9px] font-semibold uppercase text-orange-700">
        Dans la zone
      </div>
      <div v-if="data.loads.length" class="flex flex-wrap gap-1.5">
        <div
          v-for="(load, li) in data.loads"
          :key="load.id"
          class="comp-chip flex items-center gap-1 rounded-lg border border-orange-200 bg-white px-1 py-0.5 pr-1.5 shadow-sm"
          :class="load.isNew ? 'comp-chip--new' : ''"
          :style="load.isNew ? { animationDelay: `${li * 70}ms` } : undefined"
        >
          <ComponentGlyph :type="load.type" :size="26" :title="load.type" />
          <div class="min-w-0 leading-tight">
            <div class="truncate font-mono text-[10px] font-semibold text-slate-800">
              {{ load.label || load.id }}
            </div>
            <div class="text-[9px] text-slate-500">
              {{ typeLabel[load.type] || load.type }}
            </div>
          </div>
        </div>
      </div>
      <div v-else class="text-[9px] italic text-slate-400">Aucune charge / équipement</div>
    </div>
  </div>
</template>

<style scoped>
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
