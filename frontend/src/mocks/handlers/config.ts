import { http, HttpResponse } from 'msw'

const BASE_URL = 'http://localhost:8000'

export const mockConfig = {
  library: {
    library_dir: '/music_videos',
    organize_files: true,
    folder_structure: '{artist}/{album}',
  },
  apis: {
    imvdb: {
      enabled: true,
      app_key: 'test-key',
    },
    discogs: {
      enabled: true,
    },
    spotify: {
      enabled: false,
    },
  },
  logging: {
    level: 'INFO',
  },
}

export const mockConfigHistory = {
  entries: [
    {
      timestamp: '2024-01-01T10:00:00Z',
      description: 'Initial configuration',
      is_current: false,
    },
    {
      timestamp: '2024-01-02T11:00:00Z',
      description: 'Updated library settings',
      is_current: true,
    },
  ],
  current_index: 1,
  can_undo: true,
  can_redo: false,
}

export const configHandlers = [
  // Get complete config
  http.get(`${BASE_URL}/config`, () => {
    return HttpResponse.json({
      config: mockConfig,
      config_path: '/config/config.yaml',
    })
  }),

  // Get specific config field
  http.get(`${BASE_URL}/config/field/:path`, ({ params }) => {
    const path = params.path as string
    const parts = path.split('.')

    // Navigate into mockConfig to get the value
    let value: Record<string, unknown> | string | boolean | number = mockConfig
    for (const part of parts) {
      if (value && typeof value === 'object' && part in value) {
        value = value[part] as typeof value
      } else {
        return HttpResponse.json(
          { detail: `Field not found: ${path}` },
          { status: 404 }
        )
      }
    }

    return HttpResponse.json(value)
  }),

  // Update config
  http.patch(`${BASE_URL}/config`, async ({ request }) => {
    const body = (await request.json()) as {
      updates: Record<string, unknown>
      description?: string
      force?: boolean
    }

    // Check for fields that require force
    const requiresForce = Object.keys(body.updates).some(
      (key) => key.startsWith('library.') && !body.force
    )

    if (requiresForce) {
      return HttpResponse.json(
        {
          affected_fields: [
            {
              path: Object.keys(body.updates)[0],
              safety_level: 'affects_state',
              current_value: 'current',
              requested_value: Object.values(body.updates)[0],
            },
          ],
          required_actions: [
            {
              action_type: 'restart',
              target: 'server',
              description: 'Server restart required',
            },
          ],
          message: 'Configuration change requires confirmation',
        },
        { status: 409 }
      )
    }

    return HttpResponse.json({
      updated_fields: Object.keys(body.updates),
      safety_level: 'safe',
      required_actions: [],
      message: 'Configuration updated successfully',
    })
  }),

  // Get config history
  http.get(`${BASE_URL}/config/history`, () => {
    return HttpResponse.json(mockConfigHistory)
  }),

  // Undo config
  http.post(`${BASE_URL}/config/undo`, () => {
    if (!mockConfigHistory.can_undo) {
      return HttpResponse.json(
        { detail: 'Nothing to undo' },
        { status: 400 }
      )
    }

    return HttpResponse.json({
      message: 'Configuration change undone',
      new_index: 0,
      can_undo: false,
      can_redo: true,
    })
  }),

  // Redo config
  http.post(`${BASE_URL}/config/redo`, () => {
    if (!mockConfigHistory.can_redo) {
      return HttpResponse.json(
        { detail: 'Nothing to redo' },
        { status: 400 }
      )
    }

    return HttpResponse.json({
      message: 'Configuration change redone',
      new_index: 1,
      can_undo: true,
      can_redo: false,
    })
  }),

  // Get field safety level
  http.get(`${BASE_URL}/config/safety/:path`, ({ params }) => {
    const path = params.path as string

    // Return different safety levels based on path
    let safetyLevel: 'safe' | 'requires_reload' | 'affects_state' = 'safe'
    let description = 'This setting can be changed safely'

    if (path.startsWith('library.')) {
      safetyLevel = 'affects_state'
      description = 'Changing this setting affects file organization'
    } else if (path.startsWith('apis.')) {
      safetyLevel = 'requires_reload'
      description = 'Changing this setting requires server reload'
    }

    return HttpResponse.json({
      path,
      safety_level: safetyLevel,
      description,
    })
  }),
]
