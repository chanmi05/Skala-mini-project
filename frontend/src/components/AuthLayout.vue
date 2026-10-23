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
        <span class="eyebrow">INTERNAL POLICY / EMPLOYEE SERVICE</span>
        <h2>사내 지침<br />통합 조회</h2>
        <p>
          업무에 필요한 규정과 절차를 확인하는 공간입니다.<br />텍스트 또는
          음성으로 질문을 입력하세요.
        </p>
        <section class="policy-register" aria-label="주요 지침 분야">
          <div class="register-heading">
            <span>주요 지침 분야</span><AppIcon name="document" :size="16" />
          </div>
          <div class="register-row">
            <span class="register-index">01</span><strong>휴가·근태</strong
            ><span>연차 / 근무 / 복무</span>
          </div>
          <div class="register-row">
            <span class="register-index">02</span><strong>출장·경비</strong
            ><span>신청 / 증빙 / 정산</span>
          </div>
          <div class="register-row">
            <span class="register-index">03</span><strong>보안·업무</strong
            ><span>자료 / 정보 / 보안</span>
          </div>
        </section>
      </div>
      <div class="story-footer">
        <AppIcon name="shield" :size="16" /> 임직원 업무 지원
        <span>TEXT / VOICE</span>
      </div>
    </aside>
    <main class="auth-main" id="main-content">
      <RouterLink to="/" class="auth-mobile-brand">{{
        PROJECT_NAME
      }}</RouterLink>
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
