<script setup lang="ts">
import type { ProcessStep } from '../composables/useProcessing'

defineProps<{
  visible: boolean
  label: string
  steps: ProcessStep[]
  running: boolean
  error: string | null
}>()

function tone(status: string) {
  if (status === 'done') return 'bg-emerald-500'
  if (status === 'active') return 'bg-sky-500 animate-pulse'
  if (status === 'error') return 'bg-red-500'
  return 'bg-slate-300'
}

function iconFor(status: string) {
  if (status === 'done') return 'check'
  if (status === 'active') return 'clock'
  if (status === 'error') return 'close'
  return 'minus'
}
</script>

<template>
  <div
    v-if="visible"
    class="mt-3 rounded-xl border border-sky-200 bg-sky-50/80 px-3 py-2.5"
  >
    <div class="mb-2 flex items-center gap-2 text-sm font-semibold text-sky-900">
      <span v-if="running" uk-spinner="ratio: 0.55"></span>
      <span v-else uk-icon="icon: check; ratio: 0.9" class="text-emerald-600"></span>
      {{ label || 'Traitement en cours' }}
    </div>
    <ol class="m-0 flex list-none flex-wrap items-center gap-2 p-0 text-sm text-slate-600">
      <li
        v-for="(s, i) in steps"
        :key="s.id"
        class="flex items-center gap-1.5"
      >
        <span v-if="i > 0" class="text-slate-300" uk-icon="icon: arrow-right; ratio: 0.7"></span>
        <span
          class="inline-flex h-5 w-5 items-center justify-center rounded-full border border-white shadow-sm"
          :class="tone(s.status)"
        >
          <span
            class="text-white"
            :uk-icon="`icon: ${iconFor(s.status)}; ratio: 0.6`"
          ></span>
        </span>
        <span :class="{ 'font-semibold text-sky-800': s.status === 'active' }">
          {{ s.label }}
        </span>
      </li>
    </ol>
    <p v-if="error" class="mb-0 mt-2 flex items-center gap-1 text-sm text-red-600">
      <span uk-icon="icon: warning"></span>
      {{ error }}
    </p>
  </div>
</template>
