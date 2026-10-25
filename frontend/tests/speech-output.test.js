import { afterEach, beforeEach, test } from 'node:test'
import assert from 'node:assert/strict'
import { useSpeechOutput } from '../src/composables/useSpeechOutput.js'

const originalSynthesis = Object.getOwnPropertyDescriptor(
  globalThis,
  'speechSynthesis',
)
const originalUtterance = Object.getOwnPropertyDescriptor(
  globalThis,
  'SpeechSynthesisUtterance',
)
let spoken, cancellations, readers
const localKorean = { lang: 'ko-KR', localService: true }

beforeEach(() => {
  spoken = []
  cancellations = 0
  readers = []
  Object.defineProperty(globalThis, 'SpeechSynthesisUtterance', {
    configurable: true,
    value: class {
      constructor(text) {
        this.text = text
      }
    },
  })
  Object.defineProperty(globalThis, 'speechSynthesis', {
    configurable: true,
    value: {
      getVoices: () => [
        { lang: 'en-US', localService: true },
        { lang: 'ko-KR', localService: false },
        localKorean,
      ],
      speak: (utterance) => spoken.push(utterance),
      cancel: () => {
        cancellations += 1
      },
    },
  })
})

afterEach(() => {
  readers.forEach((reader) => reader.stop())
  if (originalSynthesis)
    Object.defineProperty(globalThis, 'speechSynthesis', originalSynthesis)
  else delete globalThis.speechSynthesis
  if (originalUtterance)
    Object.defineProperty(
      globalThis,
      'SpeechSynthesisUtterance',
      originalUtterance,
    )
  else delete globalThis.SpeechSynthesisUtterance
})

function reader() {
  const value = useSpeechOutput()
  readers.push(value)
  return value
}

test('답변 텍스트를 한국어 음성으로 읽고 재생 상태를 반영한다', () => {
  const output = reader()
  output.speak('사내 지침 안내입니다.', 'answer-1')
  assert.equal(spoken[0].text, '사내 지침 안내입니다.')
  assert.equal(spoken[0].lang, 'ko-KR')
  assert.equal(spoken[0].voice, localKorean)
  assert.equal(output.phase.value, 'pending')
  spoken[0].onstart()
  assert.equal(output.phase.value, 'speaking')
  assert.equal(output.activeId.value, 'answer-1')
  spoken[0].onend()
  assert.equal(output.phase.value, 'idle')
  assert.equal(output.activeId.value, null)
})

test('재생 중지 시 현재 음성과 연결된 답변을 해제한다', () => {
  const output = reader()
  output.speak('답변', 'answer-1')
  output.stop()
  assert.equal(cancellations, 1)
  assert.equal(output.activeId.value, null)
  assert.equal(output.phase.value, 'idle')
})

test('다른 답변을 읽을 때 이전 음성의 지연 이벤트를 무시한다', () => {
  const output = reader()
  output.speak('이전 답변', 'answer-1')
  const oldEnd = spoken[0].onend
  output.speak('새 답변', 'answer-2')
  oldEnd()
  assert.equal(output.activeId.value, 'answer-2')
  assert.equal(output.phase.value, 'pending')
  assert.equal(cancellations, 1)
})

test('자동 재생이 차단되면 다시 듣기 동작을 안내한다', () => {
  const output = reader()
  output.speak('답변', 'answer-1')
  spoken[0].onerror({ error: 'not-allowed' })
  assert.match(output.error.value, /다시 듣기/)
  assert.equal(output.phase.value, 'idle')
  output.speak('답변', 'answer-1')
  assert.equal(output.error.value, '')
  assert.equal(output.activeId.value, 'answer-1')
})

test('음성 출력 미지원 환경에서 텍스트 확인을 안내한다', () => {
  delete globalThis.speechSynthesis
  const output = reader()
  output.speak('답변', 'answer-1')
  assert.match(output.error.value, /텍스트로 확인/)
  assert.equal(output.activeId.value, null)
})

test('음성 목록을 불러오기 전에도 한국어로 지정해 재생한다', () => {
  globalThis.speechSynthesis.getVoices = () => []
  const output = reader()
  output.speak('답변', 'answer-1')
  assert.equal(spoken[0].lang, 'ko-KR')
  assert.equal(spoken[0].voice, null)
})

const originalAudio = Object.getOwnPropertyDescriptor(globalThis, 'Audio')
let players

function mockAudio(play = () => Promise.resolve()) {
  players = []
  Object.defineProperty(globalThis, 'Audio', {
    configurable: true,
    value: class {
      constructor(url) {
        this.url = url
        players.push(this)
      }
      play() {
        return play()
      }
      pause() {
        this.paused = true
      }
      removeAttribute() {
        this.removed = true
      }
    },
  })
}

afterEach(() => {
  if (originalAudio) Object.defineProperty(globalThis, 'Audio', originalAudio)
  else delete globalThis.Audio
})

test('서버 오디오를 8008에서 인증 쿠키와 함께 재생하고 중지 시 해제한다', () => {
  mockAudio()
  const output = reader()
  output.speak('답변', 'answer-1', '/voice-audio/test.mp3')
  assert.equal(players[0].url, 'http://localhost:8008/voice-audio/test.mp3')
  assert.equal(players[0].crossOrigin, 'use-credentials')
  assert.equal(spoken.length, 0)
  assert.equal(output.phase.value, 'pending')
  players[0].onplaying()
  assert.equal(output.phase.value, 'speaking')
  output.stop()
  assert.equal(players[0].paused, true)
  assert.equal(players[0].removed, true)
  assert.equal(output.activeId.value, null)
})

test('서버 오디오 자동 재생 차단 시 다시 듣기를 안내한다', async () => {
  mockAudio(() =>
    Promise.reject(new DOMException('blocked', 'NotAllowedError')),
  )
  const output = reader()
  output.speak('답변', 'answer-1', '/voice-audio/test.mp3')
  await Promise.resolve()
  assert.match(output.error.value, /다시 듣기/)
  assert.equal(output.phase.value, 'idle')
})

test('이전 오디오의 지연 재생 실패가 새 답변의 상태를 바꾸지 않는다', async () => {
  let rejectPlay
  mockAudio(
    () =>
      new Promise((_, reject) => {
        rejectPlay = reject
      }),
  )
  const output = reader()
  output.speak('이전', 'answer-1', '/voice-audio/old.mp3')
  output.speak('새 답변', 'answer-2')
  rejectPlay(new Error('late'))
  await Promise.resolve()
  assert.equal(output.activeId.value, 'answer-2')
  assert.equal(output.error.value, '')
})
