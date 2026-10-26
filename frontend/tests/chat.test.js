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


test('후속 질문에 세션을 유지하고 새 대화에서 종료한다', async () => {
  const bodies = []
  globalThis.fetch = async (url, options) => {
    bodies.push({ url, body: JSON.parse(options.body) })
    if (url.endsWith('/voice-session-end')) return Response.json({ ended: true })
    return Response.json({ ...answer, session_id: 'abc123' })
  }
  const chat = useChat()
  await chat.send('첫 질문')
  await chat.send('그럼 신청은?')
  assert.equal(bodies[0].body.session_id, undefined)
  assert.equal(bodies[1].body.session_id, 'abc123')
  assert.notEqual(bodies[0].body.request_id, bodies[1].body.request_id)
  assert.equal(chat.requestContext().sessionId, 'abc123')
  chat.reset()
  assert.equal(bodies[2].body.session_id, 'abc123')
  await chat.send('새 질문')
  assert.equal(bodies[3].body.session_id, undefined)
})

test('같은 실패 질문의 재전송은 request_id를 재사용한다', async () => {
  const ids = []
  globalThis.fetch = async (_, options) => {
    ids.push(JSON.parse(options.body).request_id)
    return ids.length === 1 ? new Response('', { status: 503 }) : Response.json(answer)
  }
  const chat = useChat()
  assert.equal(await chat.send('질문'), false)
  assert.equal(await chat.send('질문'), true)
  assert.equal(ids[0], ids[1])
})

test('문서 변경 충돌 후에는 이전 세션을 보내지 않는다', async () => {
  const bodies = []
  globalThis.fetch = async (_, options) => {
    bodies.push(JSON.parse(options.body))
    if (bodies.length === 2) return Response.json({ detail: '새 대화를 시작해 주세요.' }, { status: 409 })
    return Response.json({ ...answer, session_id: 'abc123' })
  }
  const chat = useChat()
  await chat.send('질문')
  assert.equal(await chat.send('후속 질문'), false)
  assert.equal(await chat.send('다시 질문'), true)
  assert.equal(bodies[2].session_id, undefined)
})
