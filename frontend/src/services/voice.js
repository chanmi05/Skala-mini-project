export async function transcribeAudio(audio, { signal } = {}) {
  const body = new FormData()
  body.append('audio', audio, `recording-${crypto.randomUUID()}.webm`)
  const timeout = AbortSignal.timeout(120000)
  let response
  try {
    response = await fetch('/voice-api/stt/', {
      method: 'POST',
      credentials: 'include',
      body,
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    })
  } catch (error) {
    if (signal?.aborted) throw error
    if (error.name === 'TimeoutError') {
      throw new Error(
        '음성 변환 시간이 초과되었습니다. 짧게 녹음해 다시 시도해 주세요.',
      )
    }
    throw new Error(
      '음성 서버에 연결할 수 없습니다. 서버 실행 상태를 확인해 주세요.',
    )
  }
  if (response.status === 401) {
    throw new Error('음성 질문을 사용하려면 다시 로그인해 주세요.')
  }
  if (!response.ok) {
    throw new Error(
      '음성 변환을 처리하지 못했습니다. 음성 서버 실행 상태를 확인해 주세요.',
    )
  }
  const data = await response.json().catch(() => null)
  if (data?.error)
    throw new Error('음성 변환에 실패했습니다. 다시 녹음해 주세요.')
  if (typeof data?.text !== 'string' || !data.text.trim()) {
    throw new Error(
      '음성을 인식하지 못했습니다. 마이크를 확인하고 다시 녹음해 주세요.',
    )
  }
  return data.text.trim()
}
