/**
 * Lightweight JWT decode utility.
 *
 * Decodes the payload of a JWT token without verification.
 * Verification is handled server-side; this is only for reading
 * claims like `exp` for token expiry scheduling.
 */

export interface JwtPayload {
  /** Subject (username) */
  sub?: string
  /** User ID */
  user_id?: number
  /** Expiration timestamp (Unix seconds) */
  exp?: number
  /** Issued at timestamp (Unix seconds) */
  iat?: number
  /** JWT ID */
  jti?: string
  /** Token type (access or refresh) */
  type?: string
}

/**
 * Decode a JWT token and return the payload.
 *
 * This does NOT verify the token signature. Verification is done
 * by the backend. This is used for reading claims like `exp` for
 * proactive token refresh scheduling.
 *
 * @param token - The JWT token string
 * @returns The decoded payload, or null if decoding fails
 */
export function decodeJwt(token: string): JwtPayload | null {
  try {
    // JWT format: header.payload.signature
    const parts = token.split('.')
    if (parts.length !== 3) {
      return null
    }

    // Decode the payload (second part)
    const payload = parts[1]
    // Handle URL-safe base64 encoding
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/')
    // Pad if necessary
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
    const decoded = atob(padded)
    return JSON.parse(decoded) as JwtPayload
  } catch {
    return null
  }
}

/**
 * Check if a JWT token is expired.
 *
 * @param token - The JWT token string
 * @param bufferSeconds - Buffer time before actual expiry (default: 60 seconds)
 * @returns true if the token is expired or will expire within the buffer
 */
export function isTokenExpired(token: string, bufferSeconds = 60): boolean {
  const payload = decodeJwt(token)
  if (!payload?.exp) {
    return true // Assume expired if no expiry claim
  }

  const nowSeconds = Math.floor(Date.now() / 1000)
  return payload.exp <= nowSeconds + bufferSeconds
}

/**
 * Get the time until token expiry in milliseconds.
 *
 * @param token - The JWT token string
 * @returns Milliseconds until expiry, or 0 if expired/invalid
 */
export function getTokenExpiryMs(token: string): number {
  const payload = decodeJwt(token)
  if (!payload?.exp) {
    return 0
  }

  const nowMs = Date.now()
  const expiryMs = payload.exp * 1000
  return Math.max(0, expiryMs - nowMs)
}
