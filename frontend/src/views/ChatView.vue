<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import BrandLogo from '@/components/BrandLogo.vue'
import { checkAuth, currentUser, logout } from '@/services/auth'
import { useVoiceInput } from '@/composables/useVoiceInput'
import { useSpeechOutput } from '@/composables/useSpeechOutput'
import { useChat } from '@/composables/useChat'
import { MAX_QUESTION_LENGTH } from '@/services/voice'
import { PROJECT_NAME } from '@/config/project'

const router = useRouter()
const draft = ref('')
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
const {
  messages,
  pending,
  error: chatError,
  send: sendText,
  receiveVoiceAnswer,
  reset: resetChat,
} = useChat((answer, voice) => {
  scrollToAnswer()
  if (voice) speakAnswer(answer.content, answer.id, answer.audioUrl)
})
const {
  phase: voicePhase,
  seconds: recordingSeconds,
  error: voiceError,
  busy: voiceBusy,
  start: startVoice,
  stop: stopVoice,
  cancel: cancelVoice,
} = useVoiceInput(receiveVoiceAnswer)
const voiceStatus = computed(() => {
  if (voicePhase.value === 'requesting')
    return '마이크 사용 권한을 확인하고 있어요.'
  if (voicePhase.value === 'recording') {
    return `녹음 중 · ${recordingSeconds.value}초 / 60초 · 마이크 버튼을 눌러 종료하세요.`
  }
  if (voicePhase.value === 'transcribing')
    return '음성을 인식하고 지침 답변을 준비하고 있어요.'
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
  resetChat()
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

async function scrollToAnswer() {
  await nextTick()
  messageEnd.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })
}

async function send() {
  if (voiceBusy.value || pending.value) return
  const content = draft.value.trim()
  if (!content) return
  if (!currentUser.value) {
    chatError.value = '로그인 후 질문할 수 있습니다.'
    return
  }
  if (content.length > MAX_QUESTION_LENGTH) {
    chatError.value = '질문은 2,000자 이내로 입력해 주세요.'
    return
  }
  stopAnswer()
  speechError.value = ''
  const sending = sendText(content)
  draft.value = ''
  await nextTick()
  resizeInput()
  scrollToAnswer()
  const success = await sending
  if (success === false && chatError.value && !draft.value) {
    draft.value = content
    await nextTick()
    resizeInput()
  }
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
    resetChat()
    await router.push('/login')
  } catch (e) {
    notice.value = e.message
  } finally {
    loggingOut.value = false
  }
}

function resetVoice() {
  cancelVoice()
  stopAnswer()
  speechError.value = ''
  voiceError.value = ''
}

function toggleVoice() {
  if (pending.value) return
  if (voicePhase.value === 'recording') {
    stopVoice()
    return
  }
  stopAnswer()
  if (!currentUser.value) {
    voiceError.value = '로그인 후 음성으로 질문할 수 있습니다.'
    return
  }
  if (draft.value.trim()) {
    voiceError.value = '입력 중인 질문을 먼저 전송하거나 지운 뒤 녹음해 주세요.'
    return
  }
  chatError.value = ''
  startVoice()
}

onMounted(() => {
  checkAuth()
})
onUnmounted(() => {
  resetVoice()
  resetChat()
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
          <RouterLink v-if="!currentUser" to="/login" class="header-login"
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
                  >{{ PROJECT_NAME }}
                  <span v-if="message.mode === 'demo'">데모</span>
                  <span v-else-if="message.mode === 'mock'"
                    >연결 테스트</span
                  ></span
                >
                <p>{{ message.content }}</p>
                <div v-if="message.sources.length" class="answer-sources">
                  <strong>참고 지침</strong>
                  <ul>
                    <li v-for="(source, index) in message.sources" :key="index">
                      {{ source.doc
                      }}<template v-if="source.article">
                        · {{ source.article }}</template
                      ><template v-if="source.page != null">
                        · {{ source.page }}쪽</template
                      >
                    </li>
                  </ul>
                </div>
                <p v-if="message.needsReview" class="answer-note">
                  추가 확인이 필요한 답변입니다. 해당 지침과 함께 확인해 주세요.
                </p>
                <p v-if="message.handoff" class="answer-note">
                  정확한 안내는 담당 부서에 문의해 주세요.
                </p>
                <p v-if="message.warning" class="answer-note">
                  {{ message.warning }}
                </p>
                <button
                  type="button"
                  class="answer-audio-button"
                  :class="{ playing: speakingMessageId === message.id }"
                  :disabled="voiceBusy || pending"
                  :aria-label="
                    speakingMessageId === message.id
                      ? '음성 답변 중지'
                      : '답변 다시 듣기'
                  "
                  @click="
                    speakingMessageId === message.id
                      ? stopAnswer()
                      : speakAnswer(
                          message.content,
                          message.id,
                          message.audioUrl,
                        )
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
          <p v-if="pending" class="answer-pending" role="status">
            관련 지침을 확인하고 있습니다…
          </p>
          <div ref="messageEnd"></div>
        </section>
      </main>
      <div class="composer-area">
        <p v-if="chatError" class="voice-feedback error" role="alert">
          {{ chatError }}
        </p>
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
            :maxlength="MAX_QUESTION_LENGTH"
            placeholder="사내 지침에 대해 질문해 주세요."
            :readonly="voiceBusy || pending"
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
                :disabled="pending || (voiceBusy && voicePhase !== 'recording')"
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
                :disabled="!draft.trim() || voiceBusy || pending"
              >
                <AppIcon name="arrow" :size="20" />
              </button>
            </div>
          </div>
        </form>
        <p class="composer-disclaimer">
          질문은 2,000자까지 입력할 수 있습니다. 음성 질문은 녹음 종료 후 자동
          전송되며 답변을 음성으로 재생합니다.
        </p>
      </div>
    </div>
  </div>
</template>
