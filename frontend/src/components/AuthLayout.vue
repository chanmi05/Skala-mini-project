<script setup>
import BrandLogo from './BrandLogo.vue'
import AppIcon from './AppIcon.vue'
import { PROJECT_NAME } from '@/config/project'
</script>

<template>
  <div class="auth-layout">
    <aside class="auth-story">
      <RouterLink
        to="/"
        class="brand-link"
        :aria-label="`${PROJECT_NAME} 메인으로`"
        ><BrandLogo
      /></RouterLink>
      <div class="story-content">
        <span class="eyebrow">우리 회사 업무 도우미</span>
        <h2>회사 생활에 필요한 답을,<br />한곳에서.</h2>
        <p>휴가 신청부터 업무 규정까지.<br />궁금할 때 편하게 물어보세요.</p>
        <section class="policy-register" aria-label="주요 지침 분야">
          <div class="register-heading">
            <span>어떤 내용이 궁금하세요?</span
            ><AppIcon name="chat" :size="18" />
          </div>
          <div class="register-row">
            <AppIcon name="calendar" :size="20" /><strong>휴가·근태</strong
            ><span>연차 / 근무 / 복무</span>
          </div>
          <div class="register-row">
            <AppIcon name="receipt" :size="20" /><strong>출장·경비</strong
            ><span>신청 / 증빙 / 정산</span>
          </div>
          <div class="register-row">
            <AppIcon name="chat" :size="20" /><strong>기타</strong
            ><span>증명서 / 회의실 / 비품</span>
          </div>
        </section>
      </div>
      <div class="story-footer">
        <AppIcon name="shield" :size="16" /> 임직원 업무 지원
        <span>글로도, 말로도 편하게</span>
      </div>
    </aside>
    <main class="auth-main" id="main-content">
      <RouterLink to="/" class="auth-mobile-brand"><BrandLogo /></RouterLink>
      <RouterLink to="/" class="back-link"
        ><AppIcon name="back" :size="17" /> 메인으로 돌아가기</RouterLink
      >
      <div class="auth-form-wrap"><slot /></div>
      <p class="auth-footer">
        © {{ new Date().getFullYear() }} {{ PROJECT_NAME }}
      </p>
    </main>
  </div>
</template>
