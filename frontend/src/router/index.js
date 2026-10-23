import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '@/views/ChatView.vue'
import LoginView from '@/views/LoginView.vue'
import SignupView from '@/views/SignupView.vue'
import { PROJECT_NAME } from '@/config/project'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: ChatView,
      meta: { title: '사내 지침 챗봇' },
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { title: '로그인' },
    },
    {
      path: '/signup',
      name: 'signup',
      component: SignupView,
      meta: { title: '회원가입' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  document.title = `${to.meta.title} · ${PROJECT_NAME}`
})

export default router
