/* eslint-disable @typescript-eslint/no-explicit-any -- Config API uses dynamic types */
import { apiJson } from '../../../api/client'

// ============================================================================
// Type Definitions
// ============================================================================

export type SafetyLevel = 'safe' | 'requires_reload' | 'affects_state'

export interface RequiredAction {
  action_type: string
  target: string | null
  description: string
}

export interface ConfigResponse {
  config: Record<string, any>
  config_path: string | null
}

export interface ConfigUpdateRequest {
  updates: Record<string, any>
  description?: string
  force?: boolean
}

export interface ConfigUpdateResponse {
  updated_fields: string[]
  safety_level: SafetyLevel
  required_actions: RequiredAction[]
  message: string
}

export interface AffectedField {
  path: string
  safety_level: SafetyLevel
  current_value: any
  requested_value: any
}

export interface ConfigConflictError {
  affected_fields: AffectedField[]
  required_actions: RequiredAction[]
  message: string
}

export interface ConfigHistoryEntry {
  timestamp: string
  description: string
  is_current: boolean
}

export interface ConfigHistoryResponse {
  entries: ConfigHistoryEntry[]
  current_index: number
  can_undo: boolean
  can_redo: boolean
}

export interface ConfigUndoRedoResponse {
  message: string
  new_index: number
  can_undo: boolean
  can_redo: boolean
}

export interface SafetyLevelInfo {
  path: string
  safety_level: SafetyLevel
  description: string
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Get complete configuration.
 * GET /config
 */
export async function getConfig(): Promise<ConfigResponse> {
  return apiJson<ConfigResponse>({
    path: '/config',
  })
}

/**
 * Get specific configuration field by dot-notation path.
 * GET /config/field/{path}
 */
export async function getConfigField(path: string): Promise<any> {
  return apiJson<any>({
    path: `/config/field/${path}`,
  })
}

/**
 * Update one or more configuration fields.
 * PATCH /config
 *
 * Returns 409 Conflict if any field requires force=true.
 * The error detail will contain ConfigConflictError data.
 */
export async function updateConfig(
  request: ConfigUpdateRequest
): Promise<ConfigUpdateResponse> {
  return apiJson<ConfigUpdateResponse>({
    method: 'PATCH',
    path: '/config',
    body: request,
  })
}

/**
 * Get configuration change history.
 * GET /config/history
 */
export async function getConfigHistory(): Promise<ConfigHistoryResponse> {
  return apiJson<ConfigHistoryResponse>({
    path: '/config/history',
  })
}

/**
 * Undo last configuration change.
 * POST /config/undo
 */
export async function undoConfig(): Promise<ConfigUndoRedoResponse> {
  return apiJson<ConfigUndoRedoResponse>({
    method: 'POST',
    path: '/config/undo',
  })
}

/**
 * Redo configuration change.
 * POST /config/redo
 */
export async function redoConfig(): Promise<ConfigUndoRedoResponse> {
  return apiJson<ConfigUndoRedoResponse>({
    method: 'POST',
    path: '/config/redo',
  })
}

/**
 * Get safety level for a specific configuration field.
 * GET /config/safety/{path}
 */
export async function getFieldSafety(path: string): Promise<SafetyLevelInfo> {
  return apiJson<SafetyLevelInfo>({
    path: `/config/safety/${path}`,
  })
}
