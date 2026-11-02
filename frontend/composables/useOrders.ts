/**
 * Заказы в кабинете — то же, что «📦 Статус заказа» в боте, но из базы сайта.
 *
 * Номер для заказов фиксируется первым вводом: следующий ввод бэкенд считает
 * заявкой на смену, которую одобряет менеджер, а заказы до этого не меняются.
 */
export interface OrderPhone {
  phone: string | null
  requested_phone: string
  requested_at: string | null
}

export interface Order {
  id: number
  title: string
  color: string
  quantity: number
  full_name: string
  phone: string
  city: string
  delivery_company: string
  price: string
  paid: string
  remainder: string
  status: string
  status_final: boolean
  ordered_at: string | null
}

export function useOrders() {
  const { csrfToken } = useAuth()
  const base = '/api/v1/orders'

  function messageFrom(payload: unknown, fallback: string): string {
    if (payload && typeof payload === 'object') {
      const data = payload as Record<string, unknown>
      if (typeof data.detail === 'string') return data.detail
      const first = Object.values(data)[0]
      if (Array.isArray(first) && typeof first[0] === 'string') return first[0]
    }
    return fallback
  }

  async function request<T>(path: string, method = 'GET', body?: Record<string, unknown>): Promise<T> {
    const headers: Record<string, string> = {}
    if (method !== 'GET') {
      // Токен читаем заново перед каждым запросом: он меняется при входе.
      headers['Content-Type'] = 'application/json'
      headers['X-CSRFToken'] = csrfToken()
    }
    const response = await fetch(base + path, {
      method,
      headers,
      credentials: 'same-origin',
      body: body ? JSON.stringify(body) : undefined,
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok) throw new Error(messageFrom(payload, 'Не удалось выполнить запрос.'))
    return payload as T
  }

  return {
    orders: () => request<Order[]>('/'),
    phone: () => request<OrderPhone>('/phone/'),
    setPhone: (phone: string) => request<OrderPhone>('/phone/', 'POST', { phone }),
  }
}
