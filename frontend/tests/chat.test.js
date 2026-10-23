import { afterEach, test } from 'node:test'
import assert from 'node:assert/strict'
import { useChat } from '../src/composables/useChat.js'

const originalFetch = globalThis.fetch
const answer = {
  answer: '지침 답변입니다.',
  sources: [{ doc: '휴가 규정' }],
  needs_review: true,
  handoff: true,
  transcript: '연차 기준',
  audio_url: '/voice-audio/test.mp3',
  warning: '추가 확인',
  mode: 'demo',
  latency_ms: 10,
}
afterEach(() => {
  globalThis.fetch = originalFetch
})

test('실제 API 답변과 근거·주의사항을 대화에 표시한다', async () => {
  globalThis.fetch = async () => Response.json(answer)
  const chat = useChat()
  assert.equal(await chat.send('연차 기준'), true)
  assert.equal(chat.pending.value, false)
  assert.equal(chat.messages.value[1].content, answer.answer)
  assert.deepEqual(chat.messages.value[1].sources, answer.sources)
  assert.equal(chat.messages.value[1].handoff, true)
  assert.equal(chat.messages.value[1].needsReview, true)
  assert.equal(chat.messages.value[1].mode, 'demo')
})

test('대기 중 중복 전송을 막고 초기화 이후 늦은 응답을 버린다', async () => {
  let complete,
    signal,
    calls = 0
  globalThis.fetch = async (_, options) => {
    calls += 1
    signal = options.signal
    return new Promise((resolve) => {
      complete = resolve
    })
  }
  const chat = useChat()
  const sending = chat.send('첫 질문')
  assert.equal(await chat.send('중복 질문'), false)
  assert.equal(calls, 1)
  chat.reset()
  assert.equal(signal.aborted, true)
  complete(Response.json(answer))
  assert.equal(await sending, null)
  assert.deepEqual(chat.messages.value, [])
  assert.equal(chat.error.value, '')
})

test('서버 실패 시 가짜 답변을 추가하지 않고 재시도할 수 있다', async () => {
  globalThis.fetch = async () => new Response('', { status: 503 })
  const chat = useChat()
  assert.equal(await chat.send('질문'), false)
  assert.equal(chat.messages.value.length, 1)
  assert.equal(chat.pending.value, false)
  assert.match(chat.error.value, /답변을 처리하지 못/)
  globalThis.fetch = async () => Response.json(answer)
  assert.equal(await chat.send('질문'), true)
  assert.equal(chat.error.value, '')
})

test('음성 답변은 인식 문장과 함께 표시하고 자동 재생 콜백을 호출한다', () => {
  let spoken
  const chat = useChat((message, voice) => {
    spoken = { message, voice }
  })
  chat.receiveVoiceAnswer(answer)
  assert.equal(chat.messages.value[0].content, answer.transcript)
  assert.equal(chat.messages.value[0].voice, true)
  assert.equal(spoken.voice, true)
  assert.equal(spoken.message.audioUrl, answer.audio_url)
  chat.reset()
  assert.deepEqual(chat.messages.value, [])
})
