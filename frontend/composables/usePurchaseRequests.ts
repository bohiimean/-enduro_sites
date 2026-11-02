import type { CartLine } from '~/composables/useCart'
import type { Paginated } from '~/composables/useApi'

export interface PurchaseRequestItem {
  id: number; kind: 'bike' | 'goods'; title: string; offer: 'stock' | 'order'; offer_label: string
  quantity: number; unit_price_rub: string | null
}
export interface PurchaseRequest {
  id: number; name: string; phone: string; status: string; status_label: string; created_at: string
  items: PurchaseRequestItem[]
}
export function purchaseRequestTotal(request: PurchaseRequest): string | null {
  return request.items.some((i) => i.unit_price_rub === null) ? null
    : request.items.reduce((sum, i) => sum + Number(i.unit_price_rub) * i.quantity, 0).toFixed(2)
}
export function purchaseRequestError(error: unknown, fallback = 'Не удалось выполнить запрос.'): string {
  const data = (error as { data?: Record<string, unknown> })?.data
  if (data) {
    if (typeof data.detail === 'string') return data.detail
    const first = Object.values(data)[0]
    if (Array.isArray(first) && typeof first[0] === 'string') return first[0]
  }
  return fallback
}
export function usePurchaseRequests() {
  const { csrfToken } = useAuth()
  const baseURL = '/api/v1/requests/'
  return {
    list: (offset = 0) => $fetch<Paginated<PurchaseRequest>>(baseURL, { query: { offset } }),
    detail: (id: string) => $fetch<PurchaseRequest>(`${baseURL}${id}/`),
    contact: () => $fetch<{ name: string; phone: string }>(`${baseURL}contact/`),
    submit: (body: { name: string; phone: string; submission_key: string; items: CartLine[] }) => $fetch<PurchaseRequest>(baseURL, {
      method: 'POST', body, headers: { 'X-CSRFToken': csrfToken() },
    }),
  }
}
