export const MAX_QUESTION_LENGTH = 2000
// Development calls port 8008 directly. Production can keep a same-origin proxy.
export const VOICE_API_BASE_URL = (
  import.meta.env?.VITE_VOICE_API_BASE_URL ||
  (import.meta.env?.PROD ? '/voice-api' : 'http://localhost:8008')
).replace(/\/+$/, '')

export class VoiceApiError extends Error {
  constructor(message, status = 0) {
    super(message)
    this.status = status
  }
}

async function request(path, body, { signal, json = false } = {}) {
  const timeout = AbortSignal.timeout(120000)
  let response
  try {
    response = await fetch(`${VOICE_API_BASE_URL}${path}`, {
      method: 'POST',
      credentials: 'include',
      ...(json ? { headers: { 'Content-Type': 'application/json' } } : {}),
      body: json ? JSON.stringify(body) : body,
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new VoiceApiError(
      error.name === 'TimeoutError'
        ? '답변 시간이 초과되었습니다. 잠시 후 다시 질문해 주세요.'
        : '음성 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.',
    )
  }
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    if (response.status === 401)
      throw new VoiceApiError(
        '로그인이 만료되었습니다. 다시 로그인해 주세요.',
        401,
      )
    const detail = typeof data?.detail === 'string' ? data.detail : null
    throw new VoiceApiError(
      detail ||
        (response.status === 422
          ? '질문 또는 녹음 형식을 확인해 주세요. 질문은 2,000자 이내로 입력해 주세요.'
          : '답변을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'),
      response.status,
    )
  }
  if (
    typeof data?.answer !== 'string' ||
    !data.answer.trim() ||
    !Array.isArray(data.sources) ||
    data.sources.some((source) => !source || typeof source.doc !== 'string') ||
    typeof data.transcript !== 'string' ||
    typeof data.needs_review !== 'boolean' ||
    typeof data.handoff !== 'boolean' ||
    typeof data.mode !== 'string' ||
    !Number.isInteger(data.latency_ms)
  ) {
    throw new VoiceApiError(
      '답변 응답 형식을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.',
    )
  }
  return data
}

export function queryText(question, options = {}) {
  question = question.trim()
  if (!question || question.length > MAX_QUESTION_LENGTH) {
    return Promise.reject(
      new VoiceApiError('질문은 1~2,000자로 입력해 주세요.'),
    )
  }
  return request('/voice-query-text', { question }, { ...options, json: true })
}

export function queryAudio(audio, options = {}) {
  if (!audio.size || audio.size > 10 * 1024 * 1024) {
    return Promise.reject(
      new VoiceApiError(
        '녹음 파일은 0바이트보다 크고 10MB 이하여야 합니다. 다시 녹음해 주세요.',
      ),
    )
  }
  const body = new FormData()
  body.append('audio', audio, `recording-${crypto.randomUUID()}.webm`)
  return request('/voice-query', body, options)
}

// Use the same API origin for answers and authenticated audio playback.
export function resolveVoiceAudioUrl(value) {
  if (typeof value !== 'string' || !value.trim() || value.startsWith('//'))
    throw new Error('음성 주소를 확인할 수 없습니다.')
  const origin = globalThis.location?.origin || 'http://localhost:5173'
  const api = new URL(`${VOICE_API_BASE_URL}/`, origin)
  const url = new URL(value, origin)
  if (
    ![
      origin,
      api.origin,
      'http://localhost:8008',
      'http://127.0.0.1:8008',
    ].includes(url.origin)
  )
    throw new Error('음성 주소를 확인할 수 없습니다.')
  const prefix = api.pathname.replace(/\/$/, '')
  let path = url.pathname.replace(/^\/voice-api(?=\/)/, '')
  if (prefix && path.startsWith(`${prefix}/`)) path = path.slice(prefix.length)
  return `${VOICE_API_BASE_URL}${path}${url.search}`
}
