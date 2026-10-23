<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthLayout from '@/components/AuthLayout.vue'
import AppIcon from '@/components/AppIcon.vue'
import { signup } from '@/services/auth'

const router = useRouter()
const name = ref('')
const employeeId = ref('')
const password = ref('')
const confirmation = ref('')
const showPassword = ref(false)
const busy = ref(false)
const error = ref('')

async function submit() {
  if (busy.value) return
  error.value = ''
  if (!name.value.trim() || !employeeId.value.trim()) {
    error.value = '이름과 사원번호를 입력해 주세요.'
    return
  }
  if (/\s/.test(employeeId.value.trim())) {
    error.value = '사원번호에는 공백을 사용할 수 없습니다.'
    return
  }
  if (password.value !== confirmation.value) {
    error.value = '비밀번호가 일치하지 않습니다.'
    return
  }
  if (password.value !== password.value.trim()) {
    error.value = '비밀번호 앞뒤의 공백을 제거해 주세요.'
    return
  }
  if (new TextEncoder().encode(password.value).length > 72) {
    error.value =
      '비밀번호가 너무 깁니다. 한글 등 다국어 문자를 포함했다면 길이를 줄여 주세요.'
    return
  }
  busy.value = true
  try {
    await signup(name.value.trim(), employeeId.value.trim(), password.value)
    await router.push({ name: 'login', query: { registered: '1' } })
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AuthLayout class="registration-layout">
    <div class="form-heading">
      <span class="form-eyebrow">ACCOUNT REGISTRATION</span>
      <h1>임직원 계정 등록</h1>
      <p>이름과 회사에서 발급한 사원번호를 입력해 주세요.</p>
    </div>
    <form class="auth-form" @submit.prevent="submit">
      <div class="field">
        <label for="name">이름</label>
        <input
          id="name"
          v-model="name"
          name="name"
          placeholder="이름을 입력해 주세요"
          autocomplete="name"
          required
          maxlength="100"
          :disabled="busy"
        />
      </div>
      <div class="field">
        <label for="employeeId">사원번호</label
        ><input
          id="employeeId"
          v-model="employeeId"
          name="employeeId"
          placeholder="사원번호를 입력해 주세요"
          autocomplete="username"
          autocapitalize="none"
          spellcheck="false"
          required
          maxlength="100"
          :disabled="busy"
        /><span class="field-hint"
          >회사에서 발급받은 사원번호를 입력해 주세요.</span
        >
      </div>
      <div class="field">
        <label for="password">비밀번호</label>
        <div class="password-field">
          <input
            id="password"
            v-model="password"
            name="password"
            :type="showPassword ? 'text' : 'password'"
            placeholder="8자 이상 입력해 주세요"
            autocomplete="new-password"
            required
            minlength="8"
            maxlength="64"
            :disabled="busy"
          /><button
            type="button"
            class="password-toggle"
            :aria-label="showPassword ? '비밀번호 숨기기' : '비밀번호 표시'"
            :aria-pressed="showPassword"
            @click="showPassword = !showPassword"
          >
            <AppIcon :name="showPassword ? 'hidden' : 'eye'" :size="19" />
          </button>
        </div>
      </div>
      <div class="field">
        <label for="confirmation">비밀번호 확인</label
        ><input
          id="confirmation"
          v-model="confirmation"
          name="confirmation"
          :type="showPassword ? 'text' : 'password'"
          placeholder="비밀번호를 한 번 더 입력해 주세요"
          autocomplete="new-password"
          required
          :disabled="busy"
        />
      </div>
      <p v-if="error" class="form-notice error" role="alert">{{ error }}</p>
      <button class="primary-button" type="submit" :disabled="busy">
        {{ busy ? '계정 생성 중…' : '계정 만들기'
        }}<AppIcon v-if="!busy" name="right" :size="19" />
      </button>
    </form>
    <p class="auth-switch">
      이미 계정이 있으신가요? <RouterLink to="/login">로그인</RouterLink>
    </p>
    <p class="signup-note">
      <AppIcon name="shield" :size="16" /> 비밀번호는 암호화되어 안전하게
      보관됩니다.
    </p>
  </AuthLayout>
</template>
