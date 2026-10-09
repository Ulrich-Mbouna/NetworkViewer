export type ComponentType =
  | 'source'
  | 'generator'
  | 'inverter'
  | 'battery'
  | 'load'
  | 'meter'
  | 'switch'
  | 'bus'

export interface ElectricalState {
  P?: number | null
  U?: number | null
  I?: number | null
  f?: number | null
}

export interface NetworkComponent {
  id: string
  type: ComponentType
  label: string
  electrical: ElectricalState
  isNew?: boolean
}

/** @deprecated use NetworkComponent */
export type Component = NetworkComponent

export interface PowerStation {
  id: string
  label: string
  generators: NetworkComponent[]
  electrical: ElectricalState
  isNew?: boolean
}

export interface Zone {
  id: string
  label: string
  power_stations: PowerStation[]
  loads: NetworkComponent[]
  components?: NetworkComponent[]
  electrical: ElectricalState
  parent_id?: string | null
}

export interface Line {
  id: string
  from_zone: string
  to_zone: string
  kind: 'feeds' | 'connects'
  attrs: Record<string, unknown>
}

export interface NetworkModel {
  meta: { name: string; version: number }
  zones: Zone[]
  lines: Line[]
  actors: {
    groupe_electrogene?: string | null
    compteur?: string | null
    dashboard?: string | null
    consommateurs: string[]
  }
}

export interface ValidationIssue {
  code: string
  message: string
  path?: string | null
}

export interface ValidationReport {
  ok: boolean
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
}

export interface MutationOp {
  op: string
  payload: Record<string, unknown>
}

export interface Suggestion {
  id: string
  issue_code: string
  severity: 'error' | 'warning'
  title: string
  description: string
  operations: MutationOp[]
}

export interface ChatResponse {
  message: string
  operations: MutationOp[]
  network: NetworkModel
  validation: ValidationReport
  suggestions?: Suggestion[]
}

export interface ApplyOpsResponse {
  network: NetworkModel
  validation: ValidationReport
  suggestions: Suggestion[]
}
