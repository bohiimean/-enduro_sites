/**
 * Вход, регистрация, подтверждение почты кодом и сброс пароля.
 *
 * Ходим в allauth headless (`/_allauth/browser/v1/...`). Схема — обычная сессия
 * Django в httpOnly-cookie, поэтому токенов тут нет и в localStorage ничего не
 * лежит: браузер сам носит cookie, а JWT мы отклонили (CLAUDE.md, «Отклонённые
 * подходы»).
 *
 * Работает только в браузере — страницы /account/** объявлены `ssr: false`.
 *
 * Про CSRF. Любой GET к headless выставляет cookie `csrftoken`, поэтому перед
 * первым изменяющим запросом достаточно один раз спросить сессию. Делает это
 * `call()` сам — иначе легко получить 403 на первом же входе.
 */
const BASE = '/_allauth/browser/v1'

export interface AuthUser {
  id: number
  display?: string
  email?: string
  has_usable_password?: boolean
}

export interface AuthError {
  message: string
  code?: string
  param?: string
}

interface AuthPayload {
  status: number
  data?: {
    user?: AuthUser
    flows?: { id: string; is_pending?: boolean }[]
  }
  meta?: { is_authenticated?: boolean }
  errors?: AuthError[]
}

export interface AuthState {
  user: AuthUser | null
  /** Адрес не подтверждён: вход не пускает, пока не введён код из письма. */
  awaitingEmailVerification: boolean
  /**
   * Адрес, на который ушёл код. Нужен только чтобы показать его человеку на
   * странице ввода кода — сам код проверяется по сессии, а не по этому полю.
   * При перезагрузке страницы теряется, и это нормально: подтверждение
   * держится сессией Django, а не состоянием фронтенда.
   */
  pendingEmail: string
  /** Сессию уже спрашивали — чтобы middleware не гонял запрос на каждый переход. */
  ready: boolean
}

export function useAuth() {
  const state = useState<AuthState>('auth', () => ({
    user: null,
    awaitingEmailVerification: false,
    pendingEmail: '',
    ready: false,
  }))

  function readCookie(name: string): string {
    if (!import.meta.client) return ''
    const hit = document.cookie.split('; ').find((row) => row.startsWith(`${name}=`))
    return hit ? decodeURIComponent(hit.slice(name.length + 1)) : ''
  }

  function apply(payload: AuthPayload) {
    const authenticated = payload.meta?.is_authenticated === true
    state.value.user = authenticated ? payload.data?.user ?? null : null
    state.value.awaitingEmailVerification = Boolean(
      payload.data?.flows?.some((flow) => flow.id === 'verify_email' && flow.is_pending),
    )
    state.value.ready = true
  }

  async function call(
    path: string,
    options: { method?: string; body?: Record<string, unknown> } = {},
  ): Promise<AuthPayload> {
    const method = options.method ?? 'GET'
    if (method !== 'GET' && !readCookie('csrftoken')) {
      // Просто чтобы Django выдал csrftoken. Ответ тут не важен.
      await call('/auth/session')
    }

    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (method !== 'GET') headers['X-CSRFToken'] = readCookie('csrftoken')

    // Нативный fetch, а не $fetch: allauth осмысленно отвечает 400 и 401 с JSON
    // в теле, и это нужно прочитать, а не поймать как исключение.
    const response = await fetch(BASE + path, {
      method,
      headers,
      credentials: 'same-origin',
      body: options.body ? JSON.stringify(options.body) : undefined,
    })
    const payload: AuthPayload = await response
      .json()
      .catch(() => ({ status: response.status }))
    apply(payload)
    return payload
  }

  /** Первый и главный вопрос: кто пришёл. Заодно выставляет csrftoken. */
  const session = () => call('/auth/session')

  async function login(email: string, password: string) {
    state.value.pendingEmail = email
    return call('/auth/login', { method: 'POST', body: { email, password } })
  }

  async function signup(email: string, password: string) {
    state.value.pendingEmail = email
    return call('/auth/signup', { method: 'POST', body: { email, password } })
  }

  const logout = () => call('/auth/session', { method: 'DELETE' })

  /**
   * Код из письма. Эндпоинт тот же, что у подтверждения ссылкой, и параметр
   * тоже называется `key` — в режиме кода туда кладётся код.
   *
   * Удачное подтверждение отвечает 200 и сразу авторизует: так работает
   * подтверждение кодом, потому что оно происходит в том же браузере, где шла
   * регистрация. 409 означает, что подтверждать нечего — сессия с ожиданием
   * кода потерялась, надо войти заново.
   */
  const verifyEmailCode = (code: string) =>
    call('/auth/email/verify', { method: 'POST', body: { key: code.trim() } })

  /** Прислать код заново. Работает по той же сессии, вход не нужен. */
  const resendEmailCode = () =>
    call('/auth/email/verify/resend', { method: 'POST', body: {} })

  const requestPasswordReset = (email: string) =>
    call('/auth/password/request', { method: 'POST', body: { email } })

  const resetPassword = (key: string, password: string) =>
    call('/auth/password/reset', { method: 'POST', body: { key, password } })

  /** Первое сообщение об ошибке — то, что показываем человеку. */
  function firstError(payload: AuthPayload, fallback: string): string {
    return payload.errors?.[0]?.message || fallback
  }

  /** Токен для наших собственных эндпоинтов (`/api/v1/account/...`). */
  const csrfToken = () => readCookie('csrftoken')

  return {
    state,
    session,
    login,
    signup,
    logout,
    verifyEmailCode,
    resendEmailCode,
    requestPasswordReset,
    resetPassword,
    firstError,
    csrfToken,
  }
}
