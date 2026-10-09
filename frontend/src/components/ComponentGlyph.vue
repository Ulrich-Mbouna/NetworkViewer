<script setup lang="ts">
import type { ComponentType } from '../api/types'

const props = withDefaults(
  defineProps<{
    type: ComponentType | string
    size?: number
    title?: string
  }>(),
  { size: 28 },
)

const meta: Record<
  string,
  { label: string; color: string; bg: string; ring: string }
> = {
  generator: { label: 'Générateur', color: '#15803d', bg: '#dcfce7', ring: '#4ade80' },
  source: { label: 'Source', color: '#ca8a04', bg: '#fef9c3', ring: '#facc15' },
  inverter: { label: 'Onduleur', color: '#7c3aed', bg: '#ede9fe', ring: '#a78bfa' },
  battery: { label: 'Batterie', color: '#0369a1', bg: '#e0f2fe', ring: '#38bdf8' },
  load: { label: 'Charge', color: '#c2410c', bg: '#ffedd5', ring: '#fb923c' },
  meter: { label: 'Compteur', color: '#0f766e', bg: '#ccfbf1', ring: '#2dd4bf' },
  switch: { label: 'Interrupteur', color: '#be123c', bg: '#ffe4e6', ring: '#fb7185' },
  bus: { label: 'Bus', color: '#334155', bg: '#e2e8f0', ring: '#94a3b8' },
}

function m() {
  return meta[props.type] ?? meta.load
}
</script>

<template>
  <div
    class="comp-glyph inline-flex shrink-0 items-center justify-center rounded-md"
    :style="{
      width: size + 'px',
      height: size + 'px',
      background: m().bg,
      boxShadow: `inset 0 0 0 1.5px ${m().ring}`,
    }"
    :title="title || m().label"
  >
    <!-- Générateur : cercle + barres -->
    <svg
      v-if="type === 'generator'"
      :width="size * 0.72"
      :height="size * 0.72"
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle cx="12" cy="12" r="8" :stroke="m().color" stroke-width="2" />
      <path
        d="M12 6v12M8 9.5h8M8 14.5h8"
        :stroke="m().color"
        stroke-width="1.8"
        stroke-linecap="round"
      />
    </svg>

    <!-- Source / PV : soleil -->
    <svg
      v-else-if="type === 'source'"
      :width="size * 0.72"
      :height="size * 0.72"
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle cx="12" cy="12" r="4" :fill="m().color" />
      <g :stroke="m().color" stroke-width="1.8" stroke-linecap="round">
        <path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" />
      </g>
    </svg>

    <!-- Onduleur : AC/DC -->
    <svg
      v-else-if="type === 'inverter'"
      :width="size * 0.72"
      :height="size * 0.72"
      viewBox="0 0 24 24"
      fill="none"
    >
      <rect
        x="3"
        y="5"
        width="18"
        height="14"
        rx="2"
        :stroke="m().color"
        stroke-width="2"
      />
      <path
        d="M7 15V9h2.2c1.2 0 2 .7 2 1.7S10.4 12.4 9.2 12.4H7M14 12c0-1.7 1-3 2.5-3S19 10.3 19 12s-1 3-2.5 3S14 13.7 14 12z"
        :stroke="m().color"
        stroke-width="1.6"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>

    <!-- Batterie -->
    <svg
      v-else-if="type === 'battery'"
      :width="size * 0.72"
      :height="size * 0.72"
      viewBox="0 0 24 24"
      fill="none"
    >
      <rect
        x="3"
        y="7"
        width="15"
        height="10"
        rx="1.5"
        :stroke="m().color"
        stroke-width="2"
      />
      <path d="M18 10h2v4h-2" :fill="m().color" />
      <rect x="5.5" y="9.5" width="3" height="5" rx="0.5" :fill="m().color" />
      <rect x="9.5" y="9.5" width="3" height="5" rx="0.5" :fill="m().color" />
    </svg>

    <!-- Charge : losange -->
    <svg
      v-else-if="type === 'load'"
      :width="size * 0.72"
      :height="size * 0.72"
      viewBox="0 0 24 24"
      fill="none"
    >
      <path
        d="M12 3l9 9-9 9-9-9 9-9z"
        :stroke="m().color"
        stroke-width="2"
        :fill="m().bg"
      />
      <path
        d="M12 8v5M12 15.5v.5"
        :stroke="m().color"
        stroke-width="2"
        stroke-linecap="round"
      />
    </svg>

    <!-- Compteur -->
    <svg
      v-else-if="type === 'meter'"
      :width="size * 0.72"
      :height="size * 0.72"
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle cx="12" cy="12" r="8" :stroke="m().color" stroke-width="2" />
      <path
        d="M12 12l4-3"
        :stroke="m().color"
        stroke-width="2"
        stroke-linecap="round"
      />
      <circle cx="12" cy="12" r="1.5" :fill="m().color" />
      <path
        d="M8 16h8"
        :stroke="m().color"
        stroke-width="1.5"
        stroke-linecap="round"
      />
    </svg>

    <!-- Interrupteur -->
    <svg
      v-else-if="type === 'switch'"
      :width="size * 0.72"
      :height="size * 0.72"
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle cx="6" cy="12" r="2.2" :fill="m().color" />
      <circle cx="18" cy="12" r="2.2" :fill="m().color" />
      <path
        d="M8 12h4.5L16 7.5"
        :stroke="m().color"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>

    <!-- Bus : barre -->
    <svg
      v-else-if="type === 'bus'"
      :width="size * 0.72"
      :height="size * 0.72"
      viewBox="0 0 24 24"
      fill="none"
    >
      <path
        d="M4 8h16M4 12h16M4 16h16"
        :stroke="m().color"
        stroke-width="2.2"
        stroke-linecap="round"
      />
    </svg>

    <!-- Fallback -->
    <svg v-else :width="size * 0.72" :height="size * 0.72" viewBox="0 0 24 24" fill="none">
      <rect
        x="5"
        y="5"
        width="14"
        height="14"
        rx="2"
        :stroke="m().color"
        stroke-width="2"
      />
    </svg>
  </div>
</template>
