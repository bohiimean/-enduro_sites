import type { CatalogItem } from '~/composables/useApi'

export interface CartLine {
  kind: 'bike' | 'goods'
  product_id: number
  offer: 'stock' | 'order'
  quantity: number
}

const STORAGE_KEY = 'skl-cart-v1'
export const cartLineKey = (line: CartLine) => `${line.kind}:${line.product_id}:${line.offer}`

export function useCart() {
  const state = useState('purchase-cart', () => ({
    items: [] as CartLine[], submissionKey: '', pending: false, ready: false, storageFailed: false,
  }))

  function persist() {
    if (!import.meta.client) return
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
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
    state.value.submissionKey = crypto.randomUUID()
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

  function remove(line: CartLine) {
    state.value.items = state.value.items.filter((item) => cartLineKey(item) !== cartLineKey(line))
    if (!state.value.items.length) state.value.pending = false
    changed()
  }

  function beginCheckout() {
    initialize()
    state.value.pending = true
    if (!state.value.submissionKey) state.value.submissionKey = crypto.randomUUID()
    persist()
  }

  function completed(submissionKey: string) {
    // Не очищаем новые позиции, если корзину поменяли, пока запрос был в пути.
    if (submissionKey === state.value.submissionKey) {
      state.value.items = []
      state.value.submissionKey = ''
      state.value.pending = false
      persist()
    }
  }

  return {
    items: computed(() => state.value.items), count: computed(() => state.value.items.reduce((n, item) => n + item.quantity, 0)),
    pending: computed(() => state.value.pending), submissionKey: computed(() => state.value.submissionKey),
    storageFailed: computed(() => state.value.storageFailed), initialize, add, quantity, remove, beginCheckout, completed,
  }
}
