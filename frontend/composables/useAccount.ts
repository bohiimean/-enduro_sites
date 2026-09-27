/**
 * Данные кабинета: профиль и номера телефона.
 *
 * Все запросы идут от имени сессии, и бэкенд отдаёт только то, что принадлежит
 * вошедшему пользователю. Телефон в запросе ничего не открывает — по нему
 * нельзя ни найти заказ, ни узнать ФИО из чужого KYC.
 */
export interface AccountPhone {
  id: number
  phone: string
  verified: boolean
  verification_method: string
  created_at: string
}

export interface Profile {
  email: string
  email_verified: boolean
  full_name: string
  phones: AccountPhone[]
  has_verified_phone: boolean
}

export function useAccount() {
  const { csrfToken } = useAuth()
  const base = '/api/v1/account'

  /** Вытаскивает человеческий текст из ответа DRF: и `detail`, и ошибки полей. */
  function messageFrom(payload: unknown, fallback: string): string {
    if (payload && typeof payload === 'object') {
      const data = payload as Record<string, unknown>
      if (typeof data.detail === 'string') return data.detail
      const first = Object.values(data)[0]
      if (Array.isArray(first) && typeof first[0] === 'string') return first[0]
    }
    return fallback
  }

  async function request<T>(
    path: string,
    method = 'GET',
    body?: Record<string, unknown>,
  ): Promise<T> {
    const headers: Record<string, string> = {}
    if (method !== 'GET') {
      headers['Content-Type'] = 'application/json'
      headers['X-CSRFToken'] = csrfToken()
    }

    const response = await fetch(base + path, {
      method,
      headers,
      credentials: 'same-origin',
      body: body ? JSON.stringify(body) : undefined,
    })

    if (response.status === 204) return undefined as T

    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      throw new Error(messageFrom(payload, 'Не удалось выполнить запрос.'))
    }
    return payload as T
  }

  return {
    profile: () => request<Profile>('/me/'),
    saveName: (fullName: string) =>
      request<Profile>('/me/', 'PATCH', { full_name: fullName }),
    phones: () => request<AccountPhone[]>('/phones/'),
    addPhone: (phone: string) => request<AccountPhone>('/phones/', 'POST', { phone }),
    removePhone: (id: number) => request<void>(`/phones/${id}/`, 'DELETE'),
  }
}
