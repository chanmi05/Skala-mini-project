import { afterEach, beforeEach, test } from 'node:test'
import assert from 'node:assert/strict'
import {
  checkAuth,
  currentUser,
  login,
  logout,
  signup,
} from '../src/services/auth.js'

const originalFetch = globalThis.fetch
const user = { name: '홍길동', employeeId: '000123' }
let calls

function reply(body, status = 200) {
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    return Response.json(body, { status })
  }
}

beforeEach(() => {
  calls = []
  currentUser.value = null
})
afterEach(() => {
  globalThis.fetch = originalFetch
  currentUser.value = null
})

test('로그인은 사원번호를 문자열로 전송하고 서버에서 받은 이름을 표시 상태에 저장한다', async () => {
  reply({ ok: true, user })
  await login('000123', 'test-password')
  assert.equal(calls[0].url, '/api/login')
  assert.equal(calls[0].options.body.get('employeeId'), '000123')
  assert.equal(calls[0].options.body.get('username'), '000123')
  assert.equal(calls[0].options.credentials, 'include')
  assert.deepEqual(currentUser.value, user)
})

test('명세의 로그인 성공 응답 후 쿠키로 사용자 정보를 조회한다', async () => {
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    return Response.json(
      url === '/api/login'
        ? { ok: true, redirect: 'http://localhost:8008/index.html' }
        : { ok: true, via: 'session', username: '000123' },
    )
  }
  await login('000123', 'test-password')
  assert.equal(calls[1].url, '/api/auth/check')
  assert.deepEqual(currentUser.value, { name: '000123', employeeId: '000123' })
})

test('로그인 성공 이후 인증 확인이 실패하면 로그인으로 표시하지 않는다', async () => {
  globalThis.fetch = async (url) =>
    Response.json(url === '/api/login' ? { ok: true } : { ok: false }, {
      status: url === '/api/login' ? 200 : 401,
    })
  await assert.rejects(login('000123', 'password'), /사원번호 또는 비밀번호/)
  assert.equal(currentUser.value, null)
})

test('회원가입은 이름·사원번호·비밀번호를 서버에 전달한다', async () => {
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    return {
      ok: true,
      redirected: true,
      url: 'http://localhost:5173/login',
      text: async () => '<html></html>',
    }
  }
  await signup('홍길동', '000123', 'test-password')
  assert.deepEqual(Object.fromEntries(calls[0].options.body), {
    ...user,
    username: '000123',
    password: 'test-password',
  })
})

test('이미 가입된 사원번호와 잘못된 로그인 정보를 구분해 안내한다', async () => {
  reply({ ok: false, error: 'employee ID already exists' }, 400)
  await assert.rejects(
    signup('김다른', '000123', 'test-password'),
    /이미 가입된 사원번호/,
  )
  reply({ ok: false }, 401)
  await assert.rejects(
    login('000123', 'wrong-password'),
    /사원번호 또는 비밀번호/,
  )
})

test('새로고침 후 세션 확인으로 이름과 사원번호를 복원한다', async () => {
  reply({ ok: true, via: 'jwt', user })
  await checkAuth()
  assert.deepEqual(currentUser.value, user)
  assert.equal(calls[0].url, '/api/auth/check')
  reply({ ok: false }, 401)
  await checkAuth()
  assert.equal(currentUser.value, null)
})

test('로그아웃하면 이름 표시 상태를 지운다', async () => {
  currentUser.value = user
  reply({ ok: true })
  await logout()
  assert.equal(currentUser.value, null)
  assert.equal(calls[0].url, '/api/logout')
})
