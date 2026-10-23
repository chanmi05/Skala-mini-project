import { computed, ref } from 'vue'
import { queryAudio } from '../services/voice.js'

// 녹음은 저장하지 않으며 페이지를 떠날 때 cancel()을 호출합니다.
export function useVoiceInput(onAnswer) {
  const phase = ref('idle')
  const seconds = ref(0)
  const error = ref('')
  const busy = computed(() => phase.value !== 'idle')
  let generation = 0
  let stream = null
  let recorder = null
  let timer = null
  let controller = null

  function stopTracks(mediaStream) {
    mediaStream?.getTracks().forEach((track) => track.stop())
  }

  function clearTimer() {
    clearInterval(timer)
    timer = null
  }

  function cancel() {
    generation += 1
    controller?.abort()
    controller = null
    if (recorder) {
      recorder.onstop = null
      recorder.onerror = null
      recorder.ondataavailable = null
      if (recorder.state !== 'inactive') recorder.stop()
      recorder = null
    }
    stopTracks(stream)
    stream = null
    clearTimer()
    seconds.value = 0
    phase.value = 'idle'
  }

  function stop() {
    if (recorder?.state !== 'recording') return
    phase.value = 'transcribing'
    clearTimer()
    recorder.stop()
    stopTracks(stream)
  }

  async function start() {
    if (busy.value) return
    error.value = ''
    const media = globalThis.navigator?.mediaDevices
    const Recorder = globalThis.MediaRecorder
    if (!media?.getUserMedia || !Recorder) {
      error.value =
        '이 환경에서는 마이크를 사용할 수 없습니다. localhost 또는 HTTPS에서 지원되는 브라우저로 접속해 주세요.'
      return
    }
    const mimeType = ['audio/webm;codecs=opus', 'audio/webm'].find((type) =>
      Recorder.isTypeSupported(type),
    )
    if (!mimeType) {
      error.value =
        '이 브라우저의 녹음 형식은 지원하지 않습니다. Chrome 또는 Edge에서 음성 질문을 사용해 주세요.'
      return
    }

    const token = ++generation
    phase.value = 'requesting'
    try {
      const acquired = await media.getUserMedia({ audio: true })
      if (token !== generation) {
        stopTracks(acquired)
        return
      }
      stream = acquired
      const recording = new Recorder(acquired, { mimeType })
      recorder = recording
      const chunks = []
      recording.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data)
      }
      recording.onerror = () => {
        if (token !== generation) return
        cancel()
        error.value =
          '녹음 중 오류가 발생했습니다. 마이크를 확인하고 다시 시도해 주세요.'
      }
      recording.onstop = async () => {
        clearTimer()
        stopTracks(acquired)
        stream = null
        recorder = null
        if (token !== generation) return
        phase.value = 'transcribing'
        const audio = new Blob(chunks, { type: mimeType })
        if (!audio.size) {
          phase.value = 'idle'
          error.value = '녹음된 음성이 없습니다. 다시 녹음해 주세요.'
          return
        }
        controller = new AbortController()
        try {
          const answer = await queryAudio(audio, {
            signal: controller.signal,
          })
          if (token === generation) await onAnswer(answer)
        } catch (e) {
          if (token === generation) error.value = e.message
        } finally {
          if (token === generation) {
            phase.value = 'idle'
            seconds.value = 0
            controller = null
          }
        }
      }
      recording.start()
      phase.value = 'recording'
      seconds.value = 0
      timer = setInterval(() => {
        seconds.value += 1
        if (seconds.value >= 60) stop()
      }, 1000)
    } catch (e) {
      if (token !== generation) return
      cancel()
      error.value =
        e.name === 'NotAllowedError'
          ? '마이크 권한이 필요합니다. 브라우저에서 마이크 사용을 허용해 주세요.'
          : '마이크를 사용할 수 없습니다. 연결 상태와 다른 앱의 사용 여부를 확인해 주세요.'
    }
  }

  return { phase, seconds, error, busy, start, stop, cancel }
}
