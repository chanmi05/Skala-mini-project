import { afterEach, beforeEach, test } from 'node:test'
import assert from 'node:assert/strict'
import { useVoiceInput } from '../src/composables/useVoiceInput.js'

const navigatorDescriptor = Object.getOwnPropertyDescriptor(
  globalThis,
  'navigator',
)
const recorderDescriptor = Object.getOwnPropertyDescriptor(
  globalThis,
  'MediaRecorder',
)
const originalFetch = globalThis.fetch
let sessions, tracks, recordings, transcripts, uploads
const answer = {
  answer: '연차는 사내 지침에 따라 신청해 주세요.',
  sources: [],
  needs_review: false,
  handoff: false,
  transcript: '연차 신청 절차를 알려주세요.',
  mode: 'live',
  latency_ms: 100,
  audio_url: '/voice-audio/answer.mp3',
}

const review = {
  raw_transcript: '유가 휴직 신청 절차를 알려주세요.',
  corrected_question: '육아휴직 신청 절차를 알려주세요.',
  changed: true,
  confirmation_required: true,
  warning: '교정한 질문을 확인해 주세요.',
}

class FakeRecorder {
  static isTypeSupported() {
    return true
  }
  constructor() {
    this.state = 'inactive'
    recordings.push(this)
  }
  start() {
    this.state = 'recording'
  }
  stop() {
    this.state = 'inactive'
    this.finished = Promise.resolve().then(async () => {
      this.ondataavailable?.({
        data: new Blob(['test audio'], { type: 'audio/webm' }),
      })
      await this.onstop?.()
    })
  }
}

function setMedia(getUserMedia) {
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: { mediaDevices: { getUserMedia } },
  })
}

function session(getContext) {
  const voice = useVoiceInput(
    (text) => {
      transcripts.push(text)
    },
    getContext,
  )
  sessions.push(voice)
  return voice
}

beforeEach(() => {
  sessions = []
  recordings = []
  transcripts = []
  uploads = []
  tracks = [
    {
      stopped: false,
      stop() {
        this.stopped = true
      },
    },
  ]
  setMedia(async () => ({ getTracks: () => tracks }))
  Object.defineProperty(globalThis, 'MediaRecorder', {
    configurable: true,
    value: FakeRecorder,
  })
  globalThis.fetch = async (url, options) => {
    uploads.push({ url, options })
    return Response.json(url.endsWith('/voice-transcribe') ? review : answer)
  }
})

afterEach(() => {
  sessions.forEach((voice) => voice.cancel())
  if (navigatorDescriptor)
    Object.defineProperty(globalThis, 'navigator', navigatorDescriptor)
  else delete globalThis.navigator
  if (recorderDescriptor)
    Object.defineProperty(globalThis, 'MediaRecorder', recorderDescriptor)
  else delete globalThis.MediaRecorder
  globalThis.fetch = originalFetch
})

test('녹음 종료 후 원문·교정 질문을 표시하고 확인 전에는 답변을 요청하지 않는다', async () => {
  const voice = session()
  await voice.start()
  assert.equal(voice.phase.value, 'recording')
  assert.equal(uploads.length, 0)
  voice.stop()
  await recordings[0].finished
  assert.equal(tracks[0].stopped, true)
  assert.equal(uploads[0].url, '/voice-api/voice-transcribe')
  assert.equal(uploads[0].options.credentials, 'include')
  assert.match(
    uploads[0].options.body.get('audio').name,
    /^recording-.*\.webm$/,
  )
  assert.equal(uploads.length, 1)
  assert.deepEqual(transcripts, [])
  assert.deepEqual(voice.review.value, review)
  assert.equal(voice.question.value, review.corrected_question)
  assert.equal(voice.phase.value, 'reviewing')
  assert.equal(voice.busy.value, false)
})

test('녹음 취소 시 음성을 업로드하지 않고 마이크를 해제한다', async () => {
  const voice = session()
  await voice.start()
  voice.cancel()
  await recordings[0].finished
  assert.equal(tracks[0].stopped, true)
  assert.equal(uploads.length, 0)
  assert.deepEqual(transcripts, [])
  assert.equal(voice.busy.value, false)
})

test('권한 요청 중 취소한 뒤 권한이 허용되어도 녹음을 시작하지 않는다', async () => {
  let allowMicrophone
  setMedia(
    () =>
      new Promise((resolve) => {
        allowMicrophone = resolve
      }),
  )
  const voice = session()
  const starting = voice.start()
  assert.equal(voice.phase.value, 'requesting')
  voice.cancel()
  allowMicrophone({ getTracks: () => tracks })
  await starting
  assert.equal(tracks[0].stopped, true)
  assert.equal(recordings.length, 0)
  assert.equal(voice.phase.value, 'idle')
})

test('변환 중 취소하면 요청을 중단하고 늦은 결과를 입력창에 반영하지 않는다', async () => {
  let complete
  globalThis.fetch = async () =>
    new Promise((resolve) => {
      complete = resolve
    })
  const voice = session()
  await voice.start()
  voice.stop()
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(voice.phase.value, 'transcribing')
  voice.cancel()
  complete(Response.json(review))
  await recordings[0].finished
  assert.deepEqual(transcripts, [])
  assert.equal(voice.phase.value, 'idle')
})

test('마이크 권한 거부를 안내하고 다시 시도할 수 있는 상태로 돌아온다', async () => {
  setMedia(async () => {
    throw new DOMException('Denied', 'NotAllowedError')
  })
  const voice = session()
  await voice.start()
  assert.match(voice.error.value, /마이크 권한/)
  assert.equal(voice.busy.value, false)
  assert.equal(uploads.length, 0)
})

test('서버 인증이 만료되면 재로그인을 안내하고 마이크를 해제한다', async () => {
  globalThis.fetch = async () => new Response('', { status: 401 })
  const voice = session()
  await voice.start()
  voice.stop()
  await recordings[0].finished
  assert.match(voice.error.value, /다시 로그인/)
  assert.equal(tracks[0].stopped, true)
  assert.deepEqual(transcripts, [])
  assert.equal(voice.busy.value, false)
})

test('잘못된 응답이면 대화에 추가하지 않고 오류를 안내한다', async () => {
  globalThis.fetch = async () => Response.json({ answer: ' ' })
  const voice = session()
  await voice.start()
  voice.stop()
  await recordings[0].finished
  assert.match(voice.error.value, /응답 형식/)
  assert.deepEqual(transcripts, [])
})

test('음성 서버가 꺼져 있으면 연결 오류를 안내한다', async () => {
  globalThis.fetch = async () => {
    throw new TypeError('offline')
  }
  const voice = session()
  await voice.start()
  voice.stop()
  await recordings[0].finished
  assert.match(voice.error.value, /음성 서버에 연결/)
  assert.equal(voice.busy.value, false)
})

test('수정한 질문을 확인하면 텍스트 API로 보내고 음성 답변을 전달한다', async () => {
  const voice = session()
  await voice.start()
  voice.stop()
  await recordings[0].finished
  voice.question.value = '수정한 질문입니다.'
  await voice.confirm()
  assert.equal(uploads[1].url, '/voice-api/voice-query-text')
  assert.equal(uploads[1].options.credentials, 'include')
  assert.deepEqual(JSON.parse(uploads[1].options.body), {
    question: '수정한 질문입니다.',
  })
  assert.deepEqual(transcripts, [answer])
  assert.equal(voice.phase.value, 'idle')
})

test('확인한 음성 질문에도 현재 세션·요청 정보를 전달한다', async () => {
  const voice = session(() => ({
    sessionId: 'session-test',
    requestId: 'request-test',
  }))
  await voice.start()
  voice.stop()
  await recordings[0].finished
  await voice.confirm()
  assert.deepEqual(JSON.parse(uploads[1].options.body), {
    question: review.corrected_question,
    session_id: 'session-test',
    request_id: 'request-test',
  })
  assert.deepEqual(transcripts, [answer])
})

test('원문 사용은 질문만 복원하고 확인 버튼 전까지 답변을 요청하지 않는다', async () => {
  const voice = session()
  await voice.start()
  voice.stop()
  await recordings[0].finished
  voice.useOriginal()
  assert.equal(voice.question.value, review.raw_transcript)
  assert.equal(uploads.length, 1)
  await voice.confirm()
  assert.equal(
    JSON.parse(uploads[1].options.body).question,
    review.raw_transcript,
  )
})

test('확인 OFF도 인식·교정 후 교정 질문으로 자동 답변을 받는다', async () => {
  const voice = session()
  voice.requireConfirmation.value = false
  await voice.start()
  voice.stop()
  await recordings[0].finished
  assert.equal(uploads.length, 2)
  assert.equal(
    JSON.parse(uploads[1].options.body).question,
    review.corrected_question,
  )
  assert.deepEqual(transcripts, [answer])
  assert.deepEqual(voice.review.value, review)
  assert.equal(voice.phase.value, 'idle')
})

test('설정 변경은 진행 중인 녹음의 확인 여부를 바꾸지 않는다', async () => {
  const voice = session()
  await voice.start()
  voice.requireConfirmation.value = false
  voice.stop()
  await recordings[0].finished
  assert.equal(uploads.length, 1)
  assert.equal(voice.phase.value, 'reviewing')
})

test('빈 질문·길이 초과는 전송하지 않고 취소 시 확인 내용을 지운다', async () => {
  const voice = session()
  await voice.start()
  voice.stop()
  await recordings[0].finished
  voice.question.value = ' '
  await voice.confirm()
  assert.match(voice.error.value, /2,000/)
  voice.question.value = '가'.repeat(2001)
  await voice.confirm()
  assert.equal(uploads.length, 1)
  voice.cancel()
  assert.equal(voice.review.value, null)
  assert.equal(voice.question.value, '')
  assert.equal(voice.phase.value, 'idle')
})

test('답변 실패 시 확인 질문을 유지하고 다시 시도할 수 있다', async () => {
  const voice = session()
  await voice.start()
  voice.stop()
  await recordings[0].finished
  voice.question.value = '사용자가 수정한 질문'
  globalThis.fetch = async () =>
    Response.json({ detail: 'RAG 연결 오류' }, { status: 503 })
  await voice.confirm()
  assert.equal(voice.phase.value, 'reviewing')
  assert.equal(voice.question.value, '사용자가 수정한 질문')
  assert.match(voice.error.value, /RAG 연결 오류/)
  globalThis.fetch = async () => Response.json(answer)
  await voice.confirm()
  assert.equal(voice.phase.value, 'idle')
  assert.deepEqual(transcripts, [answer])
})

test('답변 요청 중 중복 확인을 막고 취소 후 늦은 답변을 버린다', async () => {
  const voice = session()
  await voice.start()
  voice.stop()
  await recordings[0].finished
  let complete,
    signal,
    count = 0
  globalThis.fetch = async (_, options) => {
    count += 1
    signal = options.signal
    return new Promise((resolve) => {
      complete = resolve
    })
  }
  const sending = voice.confirm()
  assert.equal(voice.phase.value, 'answering')
  await voice.confirm()
  assert.equal(count, 1)
  voice.cancel()
  assert.equal(signal.aborted, true)
  complete(Response.json(answer))
  await sending
  assert.deepEqual(transcripts, [])
  assert.equal(voice.review.value, null)
  assert.equal(voice.phase.value, 'idle')
})
