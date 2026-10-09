<script setup lang="ts">
import type { Suggestion, ValidationReport } from '../api/types'
import { useProcessing } from '../composables/useProcessing'
import SessionLoader from './SessionLoader.vue'

defineProps<{
  validation: ValidationReport | null
  suggestions: Suggestion[]
  applyingId?: string | null
}>()

const emit = defineEmits<{
  apply: [suggestion: Suggestion]
}>()

const { visible, label, steps, running, error } = useProcessing('diagnostics')
</script>

<template>
  <div
    class="uk-card uk-card-default uk-card-body rounded-xl border border-slate-200 shadow-sm"
  >
    <h3 class="uk-card-title flex items-center gap-2 text-lg font-semibold">
      <span
        class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-amber-200 bg-amber-50 text-amber-700"
        uk-icon="icon: warning"
      ></span>
      Diagnostics
      <span
        v-if="validation"
        class="uk-label ml-2"
        :class="validation.ok ? 'uk-label-success' : 'uk-label-danger'"
      >
        {{ validation.ok ? 'OK' : 'Erreurs' }}
      </span>
    </h3>

    <SessionLoader
      :visible="visible"
      :label="label"
      :steps="steps"
      :running="running"
      :error="error"
    />

    <div v-if="!validation" class="uk-text-muted py-4 text-center text-sm">
      Lancez une validation pour voir les alertes.
    </div>

    <template v-else>
      <div v-if="validation.errors.length" class="mb-4">
        <h4 class="mb-2 flex items-center gap-1 text-sm font-semibold text-red-600">
          <span uk-icon="icon: close"></span>
          Erreurs
        </h4>
        <ul class="m-0 list-none space-y-2 p-0">
          <li
            v-for="(e, i) in validation.errors"
            :key="'e' + i"
            class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
          >
            <code class="rounded border border-red-200 bg-red-100 px-1 text-xs">{{
              e.code
            }}</code>
            {{ e.message }}
          </li>
        </ul>
      </div>

      <div v-if="validation.warnings.length" class="mb-4">
        <h4 class="mb-2 flex items-center gap-1 text-sm font-semibold text-amber-600">
          <span uk-icon="icon: info"></span>
          Avertissements
        </h4>
        <ul class="m-0 list-none space-y-2 p-0">
          <li
            v-for="(w, i) in validation.warnings"
            :key="'w' + i"
            class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
          >
            <code class="rounded border border-amber-200 bg-amber-100 px-1 text-xs">{{
              w.code
            }}</code>
            {{ w.message }}
          </li>
        </ul>
      </div>

      <div v-if="suggestions.length" class="border-t border-slate-200 pt-3">
        <h4 class="mb-2 flex items-center gap-1 text-sm font-semibold text-sky-700">
          <span uk-icon="icon: bolt"></span>
          Suggestions
        </h4>
        <ul class="m-0 list-none space-y-3 p-0">
          <li
            v-for="s in suggestions"
            :key="s.id"
            class="rounded-xl border border-sky-200 bg-sky-50/70 px-3 py-3"
          >
            <div class="flex items-start gap-2">
              <span
                class="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-sky-200 bg-white text-sky-700"
                uk-icon="icon: happy"
              ></span>
              <div class="min-w-0 flex-1">
                <div class="text-sm font-semibold text-slate-800">{{ s.title }}</div>
                <p class="mb-2 mt-1 text-xs leading-relaxed text-slate-600">
                  {{ s.description }}
                </p>
                <button
                  class="uk-button uk-button-primary uk-button-small rounded-lg border border-sky-600"
                  type="button"
                  :disabled="applyingId === s.id || running"
                  @click="emit('apply', s)"
                >
                  <span v-if="applyingId === s.id" uk-spinner="ratio: 0.5"></span>
                  <span v-else uk-icon="icon: check"></span>
                  Appliquer
                </button>
              </div>
            </div>
          </li>
        </ul>
      </div>

      <p
        v-if="!validation.errors.length && !validation.warnings.length"
        class="m-0 flex items-center gap-2 text-sm text-emerald-600"
      >
        <span uk-icon="icon: check"></span>
        Aucun problème détecté.
      </p>
    </template>
  </div>
</template>
