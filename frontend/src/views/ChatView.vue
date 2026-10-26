<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
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
const reviewInput = ref(null)
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
  requireConfirmation,
  review: voiceReview,
  question: reviewedQuestion,
  reviewing,
  confirm: confirmVoiceQuestion,
  useOriginal,
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
    return '음성을 인식하고 질문을 교정하고 있어요.'
  if (voicePhase.value === 'answering')
    return '확인한 질문으로 지침 답변과 음성을 준비하고 있어요.'
  return ''
})
watch(reviewing, async (value) => {
  if (!value) return
  await nextTick()
  reviewInput.value?.focus()
  reviewInput.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
})
const suggestions = [
  {
    text: '연차는 어떻게 신청하나요?',
    prompt: '연차를 신청하려면 어떤 절차를 따라야 하나요?',
  },
  {
    text: '출장 경비 정산에 어떤 서류가 필요한가요?',
    prompt: '출장 경비를 정산할 때 필요한 서류와 절차가 궁금해요.',
  },
  {
    text: '사내 자료를 외부에 공유해도 되나요?',
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
  if (voiceBusy.value || reviewing.value || pending.value) return
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
          <span class="header-tag">우리 회사 업무 도우미</span>
        </div>
        <div class="header-actions">
          <button
            v-if="messages.length || draft || voiceBusy || voiceReview"
            type="button"
            class="reset-chat-button"
            aria-label="현재 대화 초기화"
            @click="resetConversation"
          >
            <AppIcon name="plus" :size="16" /><span>처음부터 질문하기</span>
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
        <section v-if="!messages.length && !voiceReview" class="welcome">
          <p class="chat-section-label">사내 지침 안내</p>
          <div class="welcome-assistant">
            <span class="assistant-avatar"><BrandLogo compact /></span>
            <div class="welcome-bubble">
              <p class="welcome-author">{{ PROJECT_NAME }}</p>
              <h1>안녕하세요. 무엇이 궁금하세요?</h1>
              <p class="welcome-description">
                휴가부터 출장, 보안 지침까지<br />회사 생활에 필요한 내용을 함께
                찾아드릴게요.
              </p>
            </div>
          </div>
          <div class="welcome-questions">
            <div class="topics-heading">
              <h2>이런 질문을 많이 찾아요</h2>
              <span>질문을 선택해 보세요</span>
            </div>
            <div class="suggestion-grid">
              <button
                v-for="item in suggestions"
                :key="item.prompt"
                class="suggestion-card"
                @click="useSuggestion(item.prompt)"
              >
                <span class="suggestion-description">{{ item.text }}</span>
              </button>
            </div>
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
        <section
          v-if="voiceReview"
          class="question-review"
          aria-labelledby="review-title"
        >
          <div class="question-review-heading">
            <h2 id="review-title">
              {{ reviewing ? '답변 전 질문 확인' : '음성 질문 확인 내용' }}
            </h2>
            <button type="button" class="voice-cancel" @click="resetVoice">
              {{ voiceBusy ? '취소' : '닫기' }}
            </button>
          </div>
          <h3>음성 인식 원문</h3>
          <p class="question-original">{{ voiceReview.raw_transcript }}</p>
          <label for="review-question">문맥을 반영한 질문</label>
          <textarea
            id="review-question"
            ref="reviewInput"
            v-model="reviewedQuestion"
            rows="3"
            :maxlength="MAX_QUESTION_LENGTH"
            :readonly="!reviewing || pending"
            aria-describedby="review-help review-warning"
          ></textarea>
          <p id="review-warning" class="question-review-note" role="status">
            {{
              voiceReview.warning ||
              (voiceReview.changed
                ? '문맥 교정 제안입니다. 원래 의도와 맞는지 확인해 주세요.'
                : '추가 교정 없이 원문을 유지했습니다.')
            }}
          </p>
          <p id="review-help" class="question-review-note">
            이름·숫자·부정 표현이 맞는지 확인해 주세요. 설정 변경은 다음
            녹음부터 적용됩니다.
          </p>
          <div v-if="reviewing" class="question-review-actions">
            <button
              type="button"
              class="secondary-button"
              :disabled="pending"
              @click="useOriginal"
            >
              원문 사용
            </button>
            <button
              type="button"
              class="primary-button"
              :disabled="pending || !reviewedQuestion.trim()"
              @click="confirmVoiceQuestion"
            >
              이 질문으로 답변 받기<AppIcon name="right" :size="16" />
            </button>
          </div>
        </section>
      </main>
      <div class="composer-area">
        <div class="question-confirmation-setting">
          <label
            ><input
              v-model="requireConfirmation"
              type="checkbox"
              role="switch"
              :disabled="voiceBusy || pending"
              aria-describedby="confirmation-help"
            />음성 질문 먼저 확인하기
            <span>{{ requireConfirmation ? '켜짐' : '꺼짐' }}</span></label
          >
          <p id="confirmation-help">
            {{
              requireConfirmation
                ? '말씀하신 내용을 확인하고 답변을 요청해요.'
                : '말씀하신 내용으로 바로 답변을 찾아드려요.'
            }}
          </p>
        </div>
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
            placeholder="궁금한 사내 지침을 물어보세요."
            :readonly="voiceBusy || reviewing || pending"
            @input="resizeInput"
            @keydown="onKeydown"
          ></textarea>
          <div class="composer-bottom">
            <span class="composer-keyboard-hint"
              >Enter로 전송 · Shift + Enter로 줄바꿈</span
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
                    ? '녹음 종료 후 질문 인식'
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
                :disabled="!draft.trim() || voiceBusy || reviewing || pending"
              >
                <AppIcon name="arrow" :size="20" />
              </button>
            </div>
          </div>
        </form>
        <p class="composer-disclaimer">
          음성으로 질문하시면 답변도 소리로 들려드려요.
        </p>
      </div>
    </div>
  </div>
</template>
