<script setup lang="ts">
import { ref } from 'vue'
import * as api from '../api/client'
import type { NetworkModel, Suggestion, ValidationReport } from '../api/types'
import { useProcessing } from '../composables/useProcessing'
import SessionLoader from './SessionLoader.vue'

const emit = defineEmits<{
  updated: [
    network: NetworkModel,
    validation: ValidationReport | null,
    suggestions?: Suggestion[],
  ]
  error: [message: string]
}>()

const { run, visible, label, steps, running, error } = useProcessing('import')
const jsonInput = ref<HTMLInputElement | null>(null)
const imageInput = ref<HTMLInputElement | null>(null)

async function onJsonChange(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    await run('Import JSON', ['Lecture', 'Envoi API', 'Validation'], async (next) => {
      const text = await file.text()
      const data = JSON.parse(text) as NetworkModel
      next()
      const network = await api.putNetwork(data)
      next()
      const validation = await api.validateNetwork()
      const suggestions = await api.getSuggestions()
      next()
      emit('updated', network, validation, suggestions)
    })
  } catch (e) {
    emit('error', e instanceof Error ? e.message : String(e))
  } finally {
    if (jsonInput.value) jsonInput.value.value = ''
  }
}

async function onImageChange(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    await run(
      'Import image',
      ['Upload', 'Gemma vision', 'Merge', 'Validation'],
      async (next) => {
        next()
        const { network, validation, suggestions } = await api.fromImage(file)
        next()
        next()
        next()
        emit('updated', network, validation, suggestions)
      },
    )
  } catch (e) {
    emit('error', e instanceof Error ? e.message : String(e))
  } finally {
    if (imageInput.value) imageInput.value.value = ''
  }
}
</script>

<template>
  <div
    class="uk-card uk-card-default uk-card-body rounded-xl border border-slate-200 shadow-sm"
  >
    <h3 class="uk-card-title flex items-center gap-2 text-lg font-semibold">
      <span
        class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-sky-200 bg-sky-50 text-sky-700"
        uk-icon="icon: cloud-upload"
      ></span>
      Import
    </h3>
    <p class="uk-text-meta mb-4 text-sm text-slate-500">
      Chargez un JSON de topologie ou une image de schéma (Gemma 4).
    </p>
    <div class="flex flex-wrap gap-3">
      <label
        class="uk-button uk-button-primary cursor-pointer rounded-lg border border-sky-600"
        :class="{ 'uk-disabled': running }"
      >
        <span uk-icon="icon: file-text"></span>
        JSON
        <input
          ref="jsonInput"
          type="file"
          accept="application/json,.json"
          class="hidden"
          :disabled="running"
          @change="onJsonChange"
        />
      </label>
      <label
        class="uk-button uk-button-secondary cursor-pointer rounded-lg border border-slate-300"
        :class="{ 'uk-disabled': running }"
      >
        <span uk-icon="icon: image"></span>
        Image
        <input
          ref="imageInput"
          type="file"
          accept="image/*"
          class="hidden"
          :disabled="running"
          @change="onImageChange"
        />
      </label>
    </div>

    <SessionLoader
      :visible="visible"
      :label="label"
      :steps="steps"
      :running="running"
      :error="error"
    />
  </div>
</template>
