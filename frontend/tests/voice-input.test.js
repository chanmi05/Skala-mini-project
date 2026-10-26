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

function session() {
  const voice = useVoiceInput((text) => {
    transcripts.push(text)
  })
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
    return Response.json(answer)
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

test('녹음 종료 후 마이크를 해제하고 인증 쿠키와 함께 음성 질의 API로 전송하고 답변을 전달한다', async () => {
  const voice = session()
  await voice.start()
  assert.equal(voice.phase.value, 'recording')
  assert.equal(uploads.length, 0)
  voice.stop()
  await recordings[0].finished
  assert.equal(tracks[0].stopped, true)
  assert.equal(uploads[0].url, '/voice-api/voice-query')
  assert.equal(uploads[0].options.credentials, 'include')
  assert.match(
    uploads[0].options.body.get('audio').name,
    /^recording-.*\.webm$/,
  )
  assert.deepEqual(transcripts, [answer])
  assert.equal(voice.phase.value, 'idle')
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
  complete(Response.json(answer))
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
