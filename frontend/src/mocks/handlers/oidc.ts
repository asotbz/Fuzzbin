import { http, HttpResponse } from 'msw'

const BASE_URL = 'http://localhost:8000'

export const oidcHandlers = [
  // OIDC config endpoint (public)
  http.get(`${BASE_URL}/auth/oidc/config`, () => {
    return HttpResponse.json({
      enabled: false,
      provider_name: 'SSO',
    })
  }),

  // OIDC start endpoint
  http.post(`${BASE_URL}/auth/oidc/start`, () => {
    return HttpResponse.json({
      auth_url: 'https://auth.example.com/authorize?state=test-state',
      state: 'test-state',
    })
  }),

  // OIDC exchange endpoint
  http.post(`${BASE_URL}/auth/oidc/exchange`, () => {
    return HttpResponse.json({
      access_token: 'oidc-access-token',
      token_type: 'bearer',
      expires_in: 1800,
    })
  }),
]
