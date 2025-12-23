import { useSyncExternalStore } from 'react'
import { getTokens, subscribe } from './tokenStore'

export function useAuthTokens() {
  return useSyncExternalStore(subscribe, getTokens, getTokens)
}
