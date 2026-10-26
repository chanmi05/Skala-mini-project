import { afterEach, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  queryText,
  queryAudio,
  transcribeAudio,
  resolveVoiceAudioUrl,
} from '../src/services/voice.js'

const originalFetch = globalThis.fetch
const answer = {
  answer: '연차 지침입니다.',
  sources: [{ doc: '취업규칙', article: '제10조', page: 3 }],
  needs_review: true,
  handoff: false,
  transcript: '연차 기준',
  audio_url: '/voice-audio/test.mp3',
  mode: 'live',
  latency_ms: 42,
}
afterEach(() => {
  globalThis.fetch = originalFetch
})

test('텍스트 질문을 JSON으로 보내고 출처와 음성 주소를 유지한다', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/voice-api/voice-query-text')
    assert.equal(options.credentials, 'include')
    assert.equal(options.headers['Content-Type'], 'application/json')
    assert.deepEqual(JSON.parse(options.body), { question: '연차 기준' })
    return Response.json(answer)
  }
  assert.deepEqual(await queryText(' 연차 기준 '), answer)
})

test('빈 질문과 2000자 초과 질문은 서버에 보내지 않는다', async () => {
  globalThis.fetch = () => assert.fail('invalid request')
  await assert.rejects(queryText(' '), /2,000/)
  await assert.rejects(queryText('가'.repeat(2001)), /2,000/)
})

test('질문 확인은 8008 음성 인식 API에 audio 파일을 보내고 교정 결과를 받는다', async () => {
  const review = {
    raw_transcript: '유가 휴직',
    corrected_question: '육아휴직',
    changed: true,
    warning: null,
  }
  globalThis.fetch = async (url, options) => {
    assert.equal(url, 'http://localhost:8008/voice-transcribe')
    assert.equal(options.credentials, 'include')
    assert.equal(options.body.get('audio').size, 5)
    return Response.json(review)
  }
  assert.deepEqual(await transcribeAudio(new Blob(['audio'])), review)
})

test('잘못된 교정 응답은 확인 화면이나 자동 답변에 사용하지 않는다', async () => {
  for (const body of [
    { answer: '다른 응답' },
    { raw_transcript: '원문', corrected_question: ' ', changed: true },
  ]) {
    globalThis.fetch = async () => Response.json(body)
    await assert.rejects(transcribeAudio(new Blob(['audio'])), /질문 확인 응답/)
  }
})

test('빈 음성과 10MB 초과 음성은 서버에 보내지 않는다', async () => {
  globalThis.fetch = () => assert.fail('invalid request')
  await assert.rejects(queryAudio(new Blob([])), /10MB/)
  await assert.rejects(queryAudio({ size: 10 * 1024 * 1024 + 1 }), /10MB/)
})

test('인증 만료와 FastAPI 문자열 오류를 안내한다', async () => {
  globalThis.fetch = async () =>
    Response.json({ detail: 'Unauthorized' }, { status: 401 })
  await assert.rejects(
    queryText('질문'),
    (e) => e.status === 401 && /로그인/.test(e.message),
  )
  globalThis.fetch = async () =>
    Response.json({ detail: 'RAG 연결 오류입니다.' }, { status: 503 })
  await assert.rejects(queryText('질문'), /RAG 연결 오류/)
})

test('FastAPI 검증 오류 배열과 일반 텍스트 오류도 처리한다', async () => {
  globalThis.fetch = async () =>
    Response.json(
      {
        detail: [
          { loc: ['body', 'question'], msg: 'too long', type: 'value_error' },
        ],
      },
      { status: 422 },
    )
  await assert.rejects(queryText('질문'), /질문 또는 녹음/)
  globalThis.fetch = async () =>
    new Response('Internal Server Error', { status: 500 })
  await assert.rejects(queryText('질문'), /답변을 처리하지 못/)
})

test('실제 답변 대신 잘못된 성공 JSON을 반환하면 오류로 처리한다', async () => {
  globalThis.fetch = async () => Response.json({ response: '다른 API 응답' })
  await assert.rejects(queryText('질문'), /응답 형식/)
})

test('상대·절대 음성 주소를 같은 출처의 인증 프록시로 정규화한다', () => {
  assert.equal(
    resolveVoiceAudioUrl('/voice-audio/test.mp3'),
    '/voice-api/voice-audio/test.mp3',
  )
  assert.equal(
    resolveVoiceAudioUrl('http://localhost:8008/voice-audio/test.mp3'),
    '/voice-api/voice-audio/test.mp3',
  )
  assert.equal(
    resolveVoiceAudioUrl('/voice-api/voice-audio/test.mp3'),
    '/voice-api/voice-audio/test.mp3',
  )
  assert.equal(
    resolveVoiceAudioUrl('http://127.0.0.1:8008/voice-audio/test.mp3'),
    '/voice-api/voice-audio/test.mp3',
  )
  assert.throws(() => resolveVoiceAudioUrl('https://unknown.example/audio.mp3'))
  assert.throws(() => resolveVoiceAudioUrl('//unknown.example/audio.mp3'))
})
