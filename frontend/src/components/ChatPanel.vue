<script setup lang="ts">
import { nextTick, ref } from 'vue'
import * as api from '../api/client'
import type { MutationOp, NetworkModel, Suggestion, ValidationReport } from '../api/types'
import { useProcessing } from '../composables/useProcessing'
import SessionLoader from './SessionLoader.vue'

const emit = defineEmits<{
  updated: [
    network: NetworkModel,
    validation: ValidationReport,
    suggestions?: Suggestion[],
  ]
  error: [message: string]
}>()

const { run, visible, label, steps, running, error } = useProcessing('chat')
const message = ref('')
const history = ref<
  {
    role: 'user' | 'assistant'
    text: string
    operations?: MutationOp[]
  }[]
>([])
const listEl = ref<HTMLElement | null>(null)

async function scrollBottom() {
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

function formatOp(op: MutationOp): string {
  const p = op.payload
  if (op.op === 'add_zone') return `+ zone ${p.id}`
  if (op.op === 'add_line') return `+ ligne ${p.id}: ${p.from_zone} → ${p.to_zone}`
  if (op.op === 'add_power_station') return `+ PS ${p.id} @ ${p.zone_id}`
  if (op.op === 'add_generator')
    return `+ générateur ${p.id} ∈ ${p.power_station_id ?? 'PS'} @ ${p.zone_id}`
  if (op.op === 'add_load') return `+ charge ${p.id} @ ${p.zone_id}`
  if (op.op === 'add_component') return `+ ${p.type ?? 'comp'} ${p.id} @ ${p.zone_id}`
  if (op.op === 'remove_zone') return `− zone ${p.id}`
  if (op.op === 'remove_line') return `− ligne ${p.id}`
  if (op.op === 'remove_power_station') return `− PS ${p.id} @ ${p.zone_id}`
  if (op.op === 'remove_generator') return `− générateur ${p.id} @ ${p.zone_id}`
  if (op.op === 'remove_load') return `− charge ${p.id} @ ${p.zone_id}`
  if (op.op === 'remove_component') return `− comp ${p.id} @ ${p.zone_id}`
  if (op.op === 'update_zone') return `✎ zone ${p.id}`
  if (op.op === 'update_line') return `✎ ligne ${p.id}`
  if (op.op === 'update_component') return `✎ comp ${p.id}`
  if (op.op === 'update_electrical') return `✎ électrique ${p.id}`
  return op.op
}

async function send() {
  const text = message.value.trim()
  if (!text || running.value) return
  history.value.push({ role: 'user', text })
  message.value = ''
  await scrollBottom()
  try {
    await run(
      'Chat Gemma',
      ['Envoi', 'Raisonnement', 'Application', 'Sync UI'],
      async (next) => {
        next()
        const res = await api.chat(text)
        next()
        next()
        // Prefer chat response network (already applied in store)
        let network = res.network
        let validation = res.validation
        let suggestions = res.suggestions ?? []
        // Double-check against store
        try {
          network = await api.getNetwork()
          validation = await api.validateNetwork()
          if (!suggestions.length) suggestions = await api.getSuggestions()
        } catch {
          /* keep res.* */
        }
        next()

        const ops = res.operations ?? []
        history.value.push({
          role: 'assistant',
          text: res.message,
          operations: ops,
        })
        // Always push network into parent — even if unchanged, forces UI refresh
        emit('updated', network, validation, suggestions)
        await scrollBottom()
      },
    )
  } catch (e) {
    const err = e instanceof Error ? e.message : String(e)
    history.value.push({ role: 'assistant', text: `Erreur: ${err}` })
    emit('error', err)
    await scrollBottom()
  }
}
</script>

<template>
  <div
    class="uk-card uk-card-default uk-card-body flex h-full flex-col rounded-xl border border-slate-200 shadow-sm"
  >
    <h3 class="uk-card-title mb-1 flex items-center gap-2 text-lg font-semibold">
      <span
        class="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-violet-200 bg-violet-50 text-violet-700"
        uk-icon="icon: commenting"
      ></span>
      Chat réseau
    </h3>
    <p class="uk-text-meta mb-3 text-sm text-slate-500">
      Décrivez une modification — seules les opérations listées modifient le graphe.
    </p>

    <div
      ref="listEl"
      class="mb-3 max-h-72 flex-1 space-y-3 overflow-y-auto rounded-xl border border-slate-200 bg-gradient-to-b from-slate-50 to-white p-3"
    >
      <div
        v-if="!history.length"
        class="flex flex-col items-center justify-center gap-2 py-8 text-center text-sm text-slate-400"
      >
        <span
          class="inline-flex h-12 w-12 items-center justify-center rounded-full border border-dashed border-slate-300 bg-white"
          uk-icon="icon: comments; ratio: 1.4"
        ></span>
        <p class="m-0">Ex. « Supprime zone5 » ou « Ajoute zone6 alimentée par zone4 »</p>
      </div>

      <div
        v-for="(m, i) in history"
        :key="i"
        class="flex gap-2"
        :class="m.role === 'user' ? 'flex-row-reverse' : 'flex-row'"
      >
        <div
          class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border shadow-sm"
          :class="
            m.role === 'user'
              ? 'border-sky-300 bg-sky-100 text-sky-700'
              : 'border-violet-300 bg-violet-100 text-violet-700'
          "
        >
          <span
            :uk-icon="
              m.role === 'user' ? 'icon: user; ratio: 0.9' : 'icon: nut; ratio: 0.9'
            "
          ></span>
        </div>
        <div
          class="max-w-[85%] rounded-2xl border px-3.5 py-2.5 text-sm leading-relaxed shadow-sm"
          :class="
            m.role === 'user'
              ? 'rounded-tr-sm border-sky-200 bg-sky-100 text-sky-950'
              : m.text.startsWith('Erreur:')
                ? 'rounded-tl-sm border-red-200 bg-red-50 text-red-800'
                : 'rounded-tl-sm border-slate-200 bg-white text-slate-800'
          "
        >
          <div class="mb-1 text-[11px] font-semibold uppercase tracking-wide opacity-70">
            {{ m.role === 'user' ? 'Vous' : 'Gemma' }}
          </div>
          <div class="whitespace-pre-wrap">{{ m.text }}</div>
          <ul
            v-if="m.operations && m.operations.length"
            class="mt-2 space-y-1 rounded-lg border border-violet-100 bg-violet-50/80 p-2"
          >
            <li
              v-for="(op, j) in m.operations"
              :key="j"
              class="flex items-center gap-1.5 font-mono text-[11px] text-violet-900"
            >
              <span uk-icon="icon: bolt; ratio: 0.7"></span>
              {{ formatOp(op) }}
            </li>
          </ul>
          <div
            v-else-if="m.role === 'assistant' && !m.text.startsWith('Erreur:')"
            class="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-800"
          >
            Aucune opération structurée → graphe inchangé
          </div>
        </div>
      </div>
    </div>

    <SessionLoader
      :visible="visible"
      :label="label"
      :steps="steps"
      :running="running"
      :error="error"
    />

    <form class="mt-3 flex gap-2" @submit.prevent="send">
      <div class="relative flex-1">
        <span
          class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          uk-icon="icon: pencil"
        ></span>
        <input
          v-model="message"
          class="uk-input rounded-xl border border-slate-300 !pl-10"
          type="text"
          placeholder="ex: Supprime zone5"
          :disabled="running"
        />
      </div>
      <button
        class="uk-button uk-button-primary rounded-xl border border-sky-600"
        type="submit"
        :disabled="running || !message.trim()"
      >
        <span v-if="running" uk-spinner="ratio: 0.55"></span>
        <span v-else uk-icon="icon: arrow-right"></span>
      </button>
    </form>
  </div>
</template>
