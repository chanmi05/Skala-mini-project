<script setup>
import { nextTick, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import { POLICY_FAQ_CATEGORIES } from '@/data/policyFaq'

defineEmits(['ask'])
const categories = POLICY_FAQ_CATEGORIES
const activeCategoryId = ref(categories[0].id)
const expandedQuestionId = ref(categories[0].questions[0].id)
const tabButtons = ref([])

function selectCategory(category) {
  if (activeCategoryId.value === category.id) return
  activeCategoryId.value = category.id
  expandedQuestionId.value = category.questions[0].id
}

async function onTabKeydown(event, index) {
  let next
  if (event.key === 'ArrowRight') next = (index + 1) % categories.length
  else if (event.key === 'ArrowLeft')
    next = (index - 1 + categories.length) % categories.length
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = categories.length - 1
  else return
  event.preventDefault()
  selectCategory(categories[next])
  await nextTick()
  tabButtons.value[next]?.focus()
}
</script>

<template>
  <section class="policy-browser" aria-labelledby="policy-browser-title">
    <div class="policy-browser-heading">
      <h1 id="policy-browser-title">사내 지침 조회</h1>
      <p>분야별로 궁금한 내용을 찾아보거나, 아래에서 바로 질문해 주세요.</p>
    </div>
    <div class="policy-tabs" role="tablist" aria-label="사내 지침 분야">
      <button
        v-for="(category, index) in categories"
        :id="`policy-tab-${category.id}`"
        :key="category.id"
        :ref="(element) => (tabButtons[index] = element)"
        type="button"
        role="tab"
        :aria-selected="activeCategoryId === category.id"
        :aria-controls="`policy-panel-${category.id}`"
        :tabindex="activeCategoryId === category.id ? 0 : -1"
        @click="selectCategory(category)"
        @keydown="onTabKeydown($event, index)"
      >
        {{ category.label }}
      </button>
    </div>
    <section
      v-for="(category, categoryIndex) in categories"
      :id="`policy-panel-${category.id}`"
      :key="category.id"
      class="policy-panel"
      :hidden="activeCategoryId !== category.id"
      role="tabpanel"
      :aria-labelledby="`policy-tab-${category.id}`"
      tabindex="0"
    >
      <header class="policy-panel-heading">
        <div>
          <p class="policy-panel-caption">자주 묻는 질문</p>
          <h2>{{ category.title }}</h2>
          <p class="policy-panel-description">{{ category.description }}</p>
        </div>
        <span class="policy-panel-index" aria-hidden="true">{{
          String(categoryIndex + 1).padStart(2, '0')
        }}</span>
      </header>
      <div class="policy-faq-list">
        <article
          v-for="(item, index) in category.questions"
          :key="item.id"
          class="policy-faq-item"
        >
          <h3>
            <button
              :id="`faq-question-${item.id}`"
              class="policy-faq-toggle"
              type="button"
              :aria-expanded="expandedQuestionId === item.id"
              :aria-controls="`faq-answer-${item.id}`"
              @click="
                expandedQuestionId =
                  expandedQuestionId === item.id ? null : item.id
              "
            >
              <span class="policy-question-index" aria-hidden="true">{{
                String(index + 1).padStart(2, '0')
              }}</span>
              <span class="policy-question-text">{{ item.question }}</span>
              <AppIcon
                :name="expandedQuestionId === item.id ? 'minus' : 'plus'"
                :size="16"
              />
            </button>
          </h3>
          <div
            :id="`faq-answer-${item.id}`"
            class="policy-faq-answer"
            :hidden="expandedQuestionId !== item.id"
            role="region"
            :aria-labelledby="`faq-question-${item.id}`"
          >
            <div class="policy-summary">
              <span class="policy-summary-label">안내 요약</span>
              <p>{{ item.summary }}</p>
            </div>
            <button
              class="policy-ask-button"
              type="button"
              :aria-label="`${item.question} 입력하기`"
              @click="$emit('ask', item.question)"
            >
              이 질문으로 문의하기<AppIcon name="right" :size="14" />
            </button>
          </div>
        </article>
      </div>
      <p class="policy-panel-note">
        일반 안내 요약입니다. 회사별 세부 기준은 사내 지침과 담당 부서에서
        확인해 주세요.
      </p>
    </section>
  </section>
</template>
