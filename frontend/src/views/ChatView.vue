<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import BrandLogo from '@/components/BrandLogo.vue'
import { checkAuth, currentUser, logout } from '@/services/auth'
import { useVoiceInput } from '@/composables/useVoiceInput'
import { useSpeechOutput } from '@/composables/useSpeechOutput'
import { PROJECT_NAME } from '@/config/project'

const router = useRouter()
const draft = ref('')
const messages = ref([])
const input = ref(null)
const messageEnd = ref(null)
const notice = ref('')
const loggingOut = ref(false)
const {
  phase: speechPhase,
  activeId: speakingMessageId,
  error: speechError,
  speak: speakAnswer,
  stop: stopAnswer,
} = useSpeechOutput()
let responseGeneration = 0
const {
  phase: voicePhase,
  seconds: recordingSeconds,
  error: voiceError,
  busy: voiceBusy,
  start: startVoice,
  stop: stopVoice,
  cancel: cancelVoice,
} = useVoiceInput(async (text) => {
  const nextDraft = [draft.value.trimEnd(), text].filter(Boolean).join('\n')
  if (nextDraft.length > 10000) {
    throw new Error(
      '질문이 너무 깁니다. 입력한 내용을 줄인 뒤 다시 녹음해 주세요.',
    )
  }
  await send({ text: nextDraft, voice: true })
})
const voiceStatus = computed(() => {
  if (voicePhase.value === 'requesting')
    return '마이크 사용 권한을 확인하고 있어요.'
  if (voicePhase.value === 'recording') {
    return `녹음 중 · ${recordingSeconds.value}초 / 60초 · 마이크 버튼을 눌러 종료하세요.`
  }
  if (voicePhase.value === 'transcribing')
    return '녹음한 질문을 텍스트로 변환하고 있어요.'
  return ''
})
const suggestions = [
  {
    icon: 'calendar',
    label: '휴가·근태',
    text: '연차 신청과 근무 기준',
    prompt: '연차를 신청하려면 어떤 절차를 따라야 하나요?',
  },
  {
    icon: 'receipt',
    label: '출장·경비',
    text: '출장 신청과 비용 정산',
    prompt: '출장 경비를 정산할 때 필요한 서류와 절차가 궁금해요.',
  },
  {
    icon: 'shield',
    label: '보안·업무',
    text: '사내 자료와 보안 지침',
    prompt: '사내 자료를 외부에 공유하려면 어떤 보안 절차를 확인해야 하나요?',
  },
]

function resizeInput() {
  if (!input.value) return
  input.value.style.height = 'auto'
  input.value.style.height = `${Math.min(input.value.scrollHeight, 180)}px`
}

function resetConversation() {
  resetVoice()
  messages.value = []
  draft.value = ''
  notice.value = ''
  nextTick(() => {
    resizeInput()
    input.value?.focus()
  })
}

async function useSuggestion(prompt) {
  resetVoice()
  draft.value = prompt
  await nextTick()
  resizeInput()
  input.value?.focus()
}

async function send({ text = draft.value, voice = false } = {}) {
  if (voiceBusy.value && !voice) return
  const content = text.trim()
  if (!content) return
  stopAnswer()
  speechError.value = ''
  const token = ++responseGeneration
  const answer = {
    id: crypto.randomUUID(),
    role: 'assistant',
    content:
      '현재는 사내 지침 챗봇의 화면 미리보기입니다. 사내 지침 문서 검색과 답변 기능은 아직 연결되지 않아, 질문하신 내용의 실제 규정을 안내할 수 없습니다.',
  }
  messages.value.push(
    { id: crypto.randomUUID(), role: 'user', content, voice },
    answer,
  )
  draft.value = ''
  await nextTick()
  resizeInput()
  messageEnd.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  input.value?.focus()
  if (voice && token === responseGeneration)
    speakAnswer(answer.content, answer.id)
}

function onKeydown(event) {
  if (
    event.key === 'Enter' &&
    !event.shiftKey &&
    !event.isComposing &&
    event.keyCode !== 229
  ) {
    event.preventDefault()
    send()
  }
}

async function signOut() {
  if (loggingOut.value) return
  loggingOut.value = true
  notice.value = ''
  resetVoice()
  try {
    await logout()
    messages.value = []
    await router.push('/login')
  } catch (e) {
    notice.value = e.message
  } finally {
    loggingOut.value = false
  }
}

function resetVoice() {
  responseGeneration += 1
  cancelVoice()
  stopAnswer()
  speechError.value = ''
  voiceError.value = ''
}

function toggleVoice() {
  if (voicePhase.value === 'recording') {
    stopVoice()
    return
  }
  stopAnswer()
  if (!currentUser.value) {
    voiceError.value = '로그인 후 음성으로 질문할 수 있습니다.'
    return
  }
  startVoice()
}

onMounted(() => {
  checkAuth()
})
onUnmounted(() => {
  resetVoice()
})
</script>

<template>
  <div class="chat-layout">
    <div class="chat-main">
      <header class="chat-header">
        <div class="header-title">
          <RouterLink
            to="/"
            class="brand-link"
            :aria-label="`${PROJECT_NAME} 메인으로`"
            ><BrandLogo
          /></RouterLink>
          <span class="header-tag">사내 지침 챗봇</span>
        </div>
        <div class="header-actions">
          <button
            v-if="messages.length || draft || voiceBusy"
            type="button"
            class="reset-chat-button"
            aria-label="현재 대화 초기화"
            @click="resetConversation"
          >
            <AppIcon name="plus" :size="16" /><span>대화 초기화</span>
          </button>
          <span class="preview-badge"
            ><span class="status-dot"></span>미리보기</span
          ><RouterLink v-if="!currentUser" to="/login" class="header-login"
            >로그인<AppIcon name="right" :size="15" /></RouterLink
          ><template v-else
            ><span class="header-user">{{ currentUser.name }}님.</span
            ><button
              type="button"
              class="icon-button"
              :disabled="loggingOut"
              aria-label="로그아웃"
              @click="signOut"
            >
              <AppIcon name="logout" :size="18" /></button
          ></template>
        </div>
      </header>
      <main
        id="main-content"
        class="chat-content"
        :class="{ 'has-messages': messages.length }"
      >
        <p v-if="notice" class="form-notice error chat-notice" role="alert">
          {{ notice }}
        </p>
        <section v-if="!messages.length" class="welcome">
          <div class="welcome-heading">
            <span class="welcome-eyebrow">POLICY WORKSPACE</span
            ><span class="workspace-caption">사내 업무 지원</span>
          </div>
          <h1>사내 지침 조회</h1>
          <p class="welcome-description">
            확인할 규정이나 절차를 질문해 주세요.<br />텍스트 입력과 음성 질문을
            지원합니다.
          </p>
          <div class="topics-heading">
            <h2>분야별 질문 예시</h2>
            <span>항목을 선택해 질문을 입력하세요</span>
          </div>
          <div class="suggestion-grid">
            <button
              v-for="(item, index) in suggestions"
              :key="item.label"
              class="suggestion-card"
              @click="useSuggestion(item.prompt)"
            >
              <span class="suggestion-index">{{
                String(index + 1).padStart(2, '0')
              }}</span>
              <span class="suggestion-title"
                ><AppIcon :name="item.icon" :size="18" /><strong>{{
                  item.label
                }}</strong></span
              >
              <span class="suggestion-description">{{ item.text }}</span>
              <AppIcon class="suggestion-arrow" name="right" :size="17" />
            </button>
          </div>
        </section>
        <section
          v-else
          class="message-list"
          aria-label="대화 내용"
          aria-live="polite"
          aria-relevant="additions"
        >
          <article
            v-for="message in messages"
            :key="message.id"
            class="message"
            :class="message.role"
          >
            <template v-if="message.role === 'assistant'"
              ><BrandLogo compact />
              <div class="message-body">
                <span class="message-author"
                  >{{ PROJECT_NAME }} <span>미리보기</span></span
                >
                <p>{{ message.content }}</p>
                <button
                  type="button"
                  class="answer-audio-button"
                  :class="{ playing: speakingMessageId === message.id }"
                  :disabled="voiceBusy"
                  :aria-label="
                    speakingMessageId === message.id
                      ? '음성 답변 중지'
                      : '답변 다시 듣기'
                  "
                  @click="
                    speakingMessageId === message.id
                      ? stopAnswer()
                      : speakAnswer(message.content, message.id)
                  "
                >
                  <AppIcon
                    :name="
                      speakingMessageId === message.id ? 'stop' : 'speaker'
                    "
                    :size="15"
                  />{{
                    speakingMessageId === message.id
                      ? speechPhase === 'pending'
                        ? '음성 준비 중 · 중지'
                        : '재생 중 · 중지'
                      : '다시 듣기'
                  }}
                </button>
              </div></template
            ><template v-else
              ><span class="sr-only">나:</span>
              <p>
                <span v-if="message.voice" class="voice-question-label"
                  ><AppIcon name="mic" :size="13" />음성 질문</span
                >{{ message.content }}
              </p></template
            >
          </article>
          <div ref="messageEnd"></div>
        </section>
      </main>
      <div class="composer-area">
        <p v-if="speechError" class="voice-feedback error" role="alert">
          {{ speechError }}
        </p>
        <p v-if="voiceError" class="voice-feedback error" role="alert">
          {{ voiceError }}
        </p>
        <div
          v-if="voiceStatus"
          class="voice-feedback"
          :class="{ recording: voicePhase === 'recording' }"
          role="status"
        >
          <span>{{ voiceStatus }}</span>
          <button
            v-if="voiceBusy"
            type="button"
            class="voice-cancel"
            @click="resetVoice"
          >
            취소
          </button>
        </div>
        <form class="composer" @submit.prevent="send">
          <label for="message" class="sr-only">사내 지침에 대해 질문하기</label
          ><textarea
            id="message"
            ref="input"
            v-model="draft"
            rows="1"
            maxlength="10000"
            placeholder="사내 지침에 대해 질문해 주세요."
            :readonly="voiceBusy"
            @input="resizeInput"
            @keydown="onKeydown"
          ></textarea>
          <div class="composer-bottom">
            <span
              ><AppIcon name="shield" :size="16" /> 사내 지침<span
                class="composer-divider"
              ></span
              ><span class="composer-mode">텍스트·음성</span></span
            >
            <div class="composer-actions">
              <button
                type="button"
                class="voice-button"
                :class="{ recording: voicePhase === 'recording' }"
                :disabled="voiceBusy && voicePhase !== 'recording'"
                :aria-pressed="voicePhase === 'recording'"
                :aria-label="
                  voicePhase === 'recording'
                    ? '녹음 종료 후 질문 전송'
                    : '음성으로 질문하기'
                "
                @click="toggleVoice"
              >
                <AppIcon
                  :name="voicePhase === 'recording' ? 'stop' : 'mic'"
                  :size="18"
                /><span>{{
                  voicePhase === 'recording' ? '녹음 종료' : '음성 질문'
                }}</span>
              </button>
              <button
                class="send-button"
                type="submit"
                aria-label="메시지 보내기"
                :disabled="!draft.trim() || voiceBusy"
              >
                <AppIcon name="arrow" :size="20" />
              </button>
            </div>
          </div>
        </form>
        <p class="composer-disclaimer">
          지침 답변 연결 준비 중 · 음성 질문은 녹음 종료 후 자동 전송되며 답변을
          음성으로 재생합니다.
        </p>
      </div>
    </div>
  </div>
</template>
