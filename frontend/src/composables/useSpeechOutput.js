import { ref } from 'vue'

export function useSpeechOutput() {
  const phase = ref('idle')
  const activeId = ref(null)
  const error = ref('')
  let utterance = null
  let generation = 0

  function stop() {
    generation += 1
    if (utterance) {
      utterance.onstart = null
      utterance.onend = null
      utterance.onerror = null
      globalThis.speechSynthesis?.cancel()
      utterance = null
    }
    phase.value = 'idle'
    activeId.value = null
  }

  function speak(text, messageId) {
    stop()
    error.value = ''
    const synthesis = globalThis.speechSynthesis
    const Utterance = globalThis.SpeechSynthesisUtterance
    if (!synthesis || !Utterance) {
      error.value =
        '이 브라우저는 음성 답변을 지원하지 않습니다. 답변을 텍스트로 확인해 주세요.'
      return
    }
    if (!text.trim()) return
    const token = generation
    const speech = new Utterance(text)
    utterance = speech
    speech.lang = 'ko-KR'
    speech.rate = 1
    const voices = synthesis.getVoices()
    const korean = voices.filter(
      (voice) => /^ko(?:-|_)/i.test(voice.lang) || voice.lang === 'ko',
    )
    speech.voice =
      korean.find((voice) => voice.localService) || korean[0] || null
    activeId.value = messageId
    phase.value = 'pending'
    speech.onstart = () => {
      if (token === generation) phase.value = 'speaking'
    }
    speech.onend = () => {
      if (token === generation) stop()
    }
    speech.onerror = (event) => {
      if (token !== generation) return
      stop()
      if (event.error === 'canceled' || event.error === 'interrupted') return
      error.value =
        event.error === 'not-allowed'
          ? '자동 재생이 차단되었습니다. 답변의 다시 듣기 버튼을 눌러 주세요.'
          : '음성 답변을 재생할 수 없습니다. 기기의 한국어 음성을 확인하거나 다시 듣기를 눌러 주세요.'
    }
    try {
      synthesis.speak(speech)
    } catch {
      stop()
      error.value = '음성 답변을 재생할 수 없습니다. 다시 듣기를 눌러 주세요.'
    }
  }

  return { phase, activeId, error, speak, stop }
}
