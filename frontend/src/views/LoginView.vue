<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthLayout from '@/components/AuthLayout.vue'
import AppIcon from '@/components/AppIcon.vue'
import { login } from '@/services/auth'

const route = useRoute()
const router = useRouter()
const employeeId = ref('')
const password = ref('')
const showPassword = ref(false)
const busy = ref(false)
const error = ref('')

async function submit() {
  if (busy.value) return
  error.value = ''
  busy.value = true
  try {
    await login(employeeId.value.trim(), password.value)
    await router.push('/')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <div class="form-heading">
      <span class="form-eyebrow">EMPLOYEE ACCESS</span>
      <h1>로그인</h1>
      <p>사원번호와 비밀번호를 입력해 주세요.</p>
    </div>
    <div
      v-if="route.query.registered === '1'"
      class="form-notice success"
      role="status"
    >
      <AppIcon name="check" :size="18" /> 회원가입이 완료되었습니다. 로그인해
      주세요.
    </div>
    <form class="auth-form" @submit.prevent="submit">
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
        />
      </div>
      <div class="field">
        <label for="password">비밀번호</label>
        <div class="password-field">
          <input
            id="password"
            v-model="password"
            name="password"
            :type="showPassword ? 'text' : 'password'"
            placeholder="비밀번호를 입력해 주세요"
            autocomplete="current-password"
            required
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
      <p v-if="error" class="form-notice error" role="alert">{{ error }}</p>
      <button class="primary-button" type="submit" :disabled="busy">
        {{ busy ? '로그인 중…' : '로그인'
        }}<AppIcon v-if="!busy" name="right" :size="19" />
      </button>
    </form>
    <p class="auth-switch">
      아직 계정이 없으신가요? <RouterLink to="/signup">회원가입</RouterLink>
    </p>
    <div class="form-divider"><span>서비스 미리보기</span></div>
    <RouterLink to="/" class="secondary-button"
      >게스트로 둘러보기<AppIcon name="right" :size="17"
    /></RouterLink>
  </AuthLayout>
</template>
