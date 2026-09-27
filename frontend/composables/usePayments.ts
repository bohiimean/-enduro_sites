/**
 * Оплата юаня: верификация плательщика (KYC) и платёж через alfabit.
 *
 * Бэкенд отдаёт только своё: номер указывается id из привязанных к аккаунту,
 * а не строкой — телефон из запроса ничего не открывает.
 */
export type KycStatus = 'not_started' | 'pending' | 'approved' | 'rejected'

export interface KycState {
  phone: string
  kyc_status: KycStatus
  /** Идёт распознавание — обычно секунды. */
  processing: boolean
  /** Заявку забрал оператор — переотправлять те же файлы нельзя. */
  manual_review: boolean
  can_upload: boolean
  documents: { doc_type: string; uploaded_at: string; low_confidence: boolean | null }[]
  limits: { per_operation_rub: string; per_day_rub: string }
}

export interface Payment {
  id: number
  external_payment_id: string
  phone: string
  amount_cny: string
  amount_rub: string
  price_per_cny: string
  status: 'created' | 'paid' | 'failed'
  status_display: string
  qr_url: string
  qr_payload: string
  /** ФИО плательщика — только на шаге QR и только тому, кто загружал паспорт. */
  payer_name: string | null
  created_at: string
  paid_at: string | null
}

export class ApiError extends Error {
  constructor(message: string, public status: number, public payload: unknown) {
    super(message)
  }
}

export function usePayments() {
  const { csrfToken } = useAuth()
  const base = '/api/v1/payments'

  function messageFrom(payload: unknown, fallback: string): string {
    if (payload && typeof payload === 'object') {
      const data = payload as Record<string, unknown>
      if (typeof data.detail === 'string') return data.detail
      const first = Object.values(data)[0]
      if (Array.isArray(first) && typeof first[0] === 'string') return first[0]
    }
    return fallback
  }

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const method = init.method ?? 'GET'
    const headers: Record<string, string> = {}
    if (method !== 'GET') {
      // Токен читаем заново перед каждым запросом: он меняется при входе.
      headers['X-CSRFToken'] = csrfToken()
      if (!(init.body instanceof FormData)) headers['Content-Type'] = 'application/json'
    }
    const response = await fetch(base + path, { ...init, headers, credentials: 'same-origin' })
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      const fallback =
        response.status === 429
          ? 'Слишком много запросов. Подождите минуту.'
          : 'Не удалось выполнить запрос.'
      throw new ApiError(messageFrom(payload, fallback), response.status, payload)
    }
    return payload as T
  }

  return {
    kyc: (phoneId: number) => request<KycState>(`/kyc/${phoneId}/`),

    uploadDocuments(phoneId: number, main: File, registration: File) {
      const form = new FormData()
      form.append('phone_id', String(phoneId))
      form.append('passport_main', main)
      form.append('passport_registration', registration)
      form.append('consent', 'true')
      return request<KycState>('/documents/', { method: 'POST', body: form })
    },

    createPayment: (phoneId: number, amountCny: string) =>
      request<Payment>('/', {
        method: 'POST',
        body: JSON.stringify({ phone_id: phoneId, amount_cny: amountCny }),
      }),

    payment: (id: number) => request<Payment>(`/${id}/`),

    payments: () => request<{ results: Payment[] }>('/?limit=10').then((page) => page.results),
  }
}
