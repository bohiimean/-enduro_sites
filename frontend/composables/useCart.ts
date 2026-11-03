import type { CatalogItem } from '~/composables/useApi'

export interface CartLine {
  kind: 'bike' | 'goods'
  product_id: number
  offer: 'stock' | 'order'
  quantity: number
}

export type RequestPaymentMethod = '' | 'cash_moscow' | 'sbp' | 'usdt'

const STORAGE_KEY = 'skl-cart-v1'
export const cartLineKey = (line: CartLine) => `${line.kind}:${line.product_id}:${line.offer}`

function submissionUuid(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  // getRandomValues доступен и при HTTP-доступе по IP, в отличие от randomUUID.
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function useCart() {
  const isOpen = useState('cart-open', () => false)
  const state = useState('purchase-cart', () => ({
    city: '', paymentMethod: '' as RequestPaymentMethod,
    items: [] as CartLine[], submissionKey: '', pending: false, ready: false, storageFailed: false,
  }))

  function persist() {
    if (!import.meta.client) return
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        city: state.value.city, paymentMethod: state.value.paymentMethod,
        items: state.value.items, submissionKey: state.value.submissionKey, pending: state.value.pending,
      }))
      state.value.storageFailed = false
    } catch { state.value.storageFailed = true }
  }

  function initialize() {
    if (!import.meta.client || state.value.ready) return
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
      if (saved && Array.isArray(saved.items)) {
        state.value.city = typeof saved.city === 'string' ? saved.city.slice(0, 150) : ''
        state.value.paymentMethod = ['cash_moscow', 'sbp', 'usdt'].includes(saved.paymentMethod) ? saved.paymentMethod : ''
        const keys = new Set<string>()
        state.value.items = saved.items.filter((item: CartLine) => {
          if (!item || !['bike', 'goods'].includes(item.kind) || !['stock', 'order'].includes(item.offer)
            || !Number.isSafeInteger(item.product_id) || item.product_id < 1
            || !Number.isInteger(item.quantity) || item.quantity < 1 || item.quantity > 99) return false
          const key = cartLineKey(item)
          if (keys.has(key)) return false
          keys.add(key)
          return true
        }).slice(0, 50).map((item: CartLine) => ({ kind: item.kind, product_id: item.product_id, offer: item.offer, quantity: item.quantity }))
        state.value.submissionKey = typeof saved.submissionKey === 'string' && /^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(saved.submissionKey) ? saved.submissionKey : ''
        state.value.pending = saved.pending === true
      }
    } catch { state.value.storageFailed = true }
    state.value.ready = true
  }

  function changed() {
    state.value.submissionKey = submissionUuid()
    persist()
  }

  function add(product: CatalogItem, offer: 'stock' | 'order') {
    initialize()
    const line: CartLine = { kind: isGoods(product) ? 'goods' : 'bike', product_id: product.id, offer, quantity: 1 }
    const available = isGoods(product) ? product.availability === offer : Boolean(product[offer])
    if (!available) return 'Это предложение больше недоступно.'
    const existing = state.value.items.find((item) => cartLineKey(item) === cartLineKey(line))
    const max = !isGoods(product) && offer === 'stock' ? Math.min(99, product.stock?.qty ?? 0) : 99
    if ((existing?.quantity ?? 0) >= max) return 'Достигнуто доступное количество.'
    if (existing) existing.quantity++
    else {
      if (state.value.items.length >= 50) return 'В корзине может быть не больше 50 позиций.'
      state.value.items.push(line)
    }
    changed()
    return ''
  }

  function quantity(line: CartLine, value: number) {
    if (!Number.isInteger(value) || value < 1 || value > 99) return
    const found = state.value.items.find((item) => cartLineKey(item) === cartLineKey(line))
    if (found && found.quantity !== value) { found.quantity = value; changed() }
  }

  function setOptions(city: string, paymentMethod: RequestPaymentMethod) {
    initialize()
    if (state.value.city === city && state.value.paymentMethod === paymentMethod) return
    state.value.city = city.slice(0, 150)
    state.value.paymentMethod = paymentMethod
    changed()
  }

  function changeOffer(line: CartLine, product: CatalogItem, offer: 'stock' | 'order') {
    if (line.offer === offer || isGoods(product) || !product[offer]) return
    const found = state.value.items.find((item) => cartLineKey(item) === cartLineKey(line))
    if (!found) return
    const other = state.value.items.find((item) => item.kind === line.kind && item.product_id === line.product_id && item.offer === offer)
    const quantity = found.quantity + (other?.quantity ?? 0)
    const max = offer === 'stock' ? Math.min(99, product.stock?.qty ?? 0) : 99
    if (quantity > max) return 'Для выбранного предложения недостаточно доступного количества.'
    if (other) {
      other.quantity = quantity
      state.value.items = state.value.items.filter((item) => item !== found)
    } else found.offer = offer
    changed()
    return ''
  }

  function remove(line: CartLine) {
    state.value.items = state.value.items.filter((item) => cartLineKey(item) !== cartLineKey(line))
    if (!state.value.items.length) state.value.pending = false
    changed()
  }

  function beginCheckout() {
    initialize()
    state.value.pending = true
    if (!state.value.submissionKey) state.value.submissionKey = submissionUuid()
    persist()
  }

  function completed(submissionKey: string) {
    // Не очищаем новые позиции, если корзину поменяли, пока запрос был в пути.
    if (submissionKey === state.value.submissionKey) {
      state.value.items = []
      state.value.submissionKey = ''
      state.value.pending = false
      state.value.city = ''
      state.value.paymentMethod = ''
      persist()
    }
  }

  return {
    isOpen, open: () => { initialize(); isOpen.value = true }, close: () => { isOpen.value = false },
    city: computed(() => state.value.city), paymentMethod: computed(() => state.value.paymentMethod), setOptions, changeOffer,
    items: computed(() => state.value.items), count: computed(() => state.value.items.reduce((n, item) => n + item.quantity, 0)),
    pending: computed(() => state.value.pending), submissionKey: computed(() => state.value.submissionKey),
    storageFailed: computed(() => state.value.storageFailed), initialize, add, quantity, remove, beginCheckout, completed,
  }
}
