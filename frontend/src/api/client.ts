import type {
  ApplyOpsResponse,
  ChatResponse,
  MutationOp,
  NetworkModel,
  Suggestion,
  ValidationReport,
} from './types'

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json() as Promise<T>
}

export async function getNetwork(): Promise<NetworkModel> {
  return handle(await fetch('/api/network'))
}

export async function putNetwork(network: NetworkModel): Promise<NetworkModel> {
  return handle(
    await fetch('/api/network', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(network),
    }),
  )
}

export async function validateNetwork(): Promise<ValidationReport> {
  return handle(await fetch('/api/validate'))
}

export async function getSuggestions(): Promise<Suggestion[]> {
  return handle(await fetch('/api/suggestions'))
}

export async function applyOps(operations: MutationOp[]): Promise<ApplyOpsResponse> {
  return handle(
    await fetch('/api/ops', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operations }),
    }),
  )
}

export async function chat(message: string): Promise<ChatResponse> {
  return handle(
    await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    }),
  )
}

export async function fromImage(file: File): Promise<{
  network: NetworkModel
  validation: ValidationReport
  suggestions?: Suggestion[]
}> {
  const form = new FormData()
  form.append('file', file)
  return handle(
    await fetch('/api/network/from-image', {
      method: 'POST',
      body: form,
    }),
  )
}

export async function downloadExcalidraw(): Promise<void> {
  const res = await fetch('/api/export/excalidraw')
  if (!res.ok) throw new Error('Échec export Excalidraw')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'reseau.excalidraw'
  a.click()
  URL.revokeObjectURL(url)
}
