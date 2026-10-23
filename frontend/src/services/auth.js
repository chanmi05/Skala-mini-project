import { ref } from 'vue'

export const currentUser = ref(null)

async function request(path, fields) {
  let response
  try {
    response = await fetch(path, {
      method: fields ? 'POST' : 'GET',
      credentials: 'include',
      ...(fields ? { body: new URLSearchParams(fields) } : {}),
      signal: AbortSignal.timeout(8000),
    })
  } catch {
    throw new Error('서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.')
  }
  const text = await response.text()
  let data = null
  try {
    data = JSON.parse(text)
  } catch {
    /* 가입·로그아웃은 HTML로 리다이렉트됩니다. */
  }
  if (!response.ok) {
    if (response.status === 401)
      throw new Error('사원번호 또는 비밀번호를 확인해 주세요.')
    if (
      text.includes('employee ID already exists') ||
      text.includes('username already exists')
    )
      throw new Error('이미 가입된 사원번호입니다.')
    if (data?.error === 'invalid registration fields')
      throw new Error('이름·사원번호와 비밀번호 형식을 확인해 주세요.')
    if (response.status >= 500)
      throw new Error(
        '인증 서버에 연결할 수 없습니다. 서버 실행 상태를 확인해 주세요.',
      )
    throw new Error('요청을 처리하지 못했습니다. 입력 내용을 확인해 주세요.')
  }
  return { data, response }
}

function readUser(data) {
  const user = data?.user
  const employeeId = user?.employeeId || data?.username
  if (typeof employeeId !== 'string' || !employeeId.trim()) return null
  const name =
    typeof user?.name === 'string' && user.name.trim()
      ? user.name.trim()
      : employeeId
  return { name, employeeId }
}

export async function login(employeeId, password) {
  // username is the documented field; employeeId supports the current Java server.
  const { data } = await request('/api/login', {
    username: employeeId,
    employeeId,
    password,
  })
  if (!data?.ok)
    throw new Error('로그인 응답을 확인할 수 없습니다. 다시 시도해 주세요.')
  let user = readUser(data)
  if (!user) {
    const { data: session } = await request('/api/auth/check')
    user = session?.ok ? readUser(session) : null
  }
  if (!user)
    throw new Error('로그인 상태를 확인할 수 없습니다. 다시 시도해 주세요.')
  currentUser.value = user
}

export async function signup(name, employeeId, password) {
  const { response } = await request('/api/signup', {
    name,
    username: employeeId,
    employeeId,
    password,
  })
  if (!response.redirected || new URL(response.url).pathname !== '/login') {
    throw new Error('회원가입 응답을 확인할 수 없습니다. 다시 시도해 주세요.')
  }
}

export async function checkAuth() {
  try {
    const { data } = await request('/api/auth/check')
    currentUser.value = data?.ok ? readUser(data) : null
  } catch {
    currentUser.value = null
  }
}

export async function logout() {
  await request('/api/logout', {})
  currentUser.value = null
}
