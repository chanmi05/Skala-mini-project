import { ref } from 'vue'
import { MAX_QUESTION_LENGTH, queryText, endRagSession } from '../services/voice.js'

export function useChat(onAnswer = () => {}) {
  const messages = ref([])
  const pending = ref(false)
  const error = ref('')
  let controller = null
  let generation = 0
  let sessionId = null
  let retry = null

  function requestContext() {
    return { sessionId, requestId: crypto.randomUUID() }
  }

  function appendAnswer(result) {
    if (result.session_id) sessionId = result.session_id
    const message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: result.answer,
      sources: result.sources,
      needsReview: result.needs_review,
      handoff: result.handoff,
      warning: result.warning,
      audioUrl: result.audio_url,
      mode: result.mode,
    }
    messages.value.push(message)
    return message
  }

  async function send(text) {
    if (pending.value) return false
    error.value = ''
    const content = text.trim()
    if (!content) return false
    if (content.length > MAX_QUESTION_LENGTH) {
      error.value = '질문은 2,000자 이내로 입력해 주세요.'
      return false
    }
    const token = ++generation
    controller = new AbortController()
    pending.value = true
    messages.value.push({ id: crypto.randomUUID(), role: 'user', content })
    try {
      const requestId = retry?.question === content ? retry.requestId : crypto.randomUUID()
      retry = { question: content, requestId }
      const result = await queryText(content, { signal: controller.signal, sessionId, requestId })
      if (token !== generation) return null
      const answer = appendAnswer(result)
      retry = null
      onAnswer(answer, false)
      return true
    } catch (e) {
      if (token !== generation) return null
      if ([404, 409, 410].includes(e.status)) {
        sessionId = null
        retry = null
      }
      error.value = e.message
      return false
    } finally {
      if (token === generation) {
        pending.value = false
        controller = null
      }
    }
  }

  function receiveVoiceAnswer(result) {
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'user',
      content: result.transcript,
      voice: true,
    })
    const answer = appendAnswer(result)
    onAnswer(answer, true)
  }

  function reset() {
    const previous = sessionId
    sessionId = null
    retry = null
    if (previous) endRagSession(previous).catch(() => {})
    generation += 1
    controller?.abort()
    controller = null
    pending.value = false
    messages.value = []
    error.value = ''
  }

  return { messages, pending, error, send, receiveVoiceAnswer, reset, requestContext }
}
