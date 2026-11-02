import type { CatalogItem, Goods, Product } from '~/composables/useApi'

export interface CartRow { line: import('~/composables/useCart').CartLine; product: CatalogItem | null | undefined; available: boolean; max: number; price: string | null }

export function useCartCatalog() {
  const cart = useCart()
  const baseURL = useApiBase()
  const products = ref<Record<string, CatalogItem | null>>({})
  const loading = ref(true)
  const error = ref('')
  let revision = 0
  const identities = computed(() => [...new Set(cart.items.value.map((i) => `${i.kind}:${i.product_id}`))].join(','))

  async function refresh() {
    const current = ++revision
    loading.value = true
    error.value = ''
    const entries = await Promise.all(identities.value.split(',').filter(Boolean).map(async (key) => {
      const [kind, id] = key.split(':')
      try {
        const product = await $fetch<Product | Goods>(`/catalog/${kind === 'bike' ? 'products' : 'goods'}/by-id/${id}/`, { baseURL })
        return [key, product] as const
      } catch (e) {
        if ((e as { statusCode?: number }).statusCode !== 404 && current === revision) error.value = 'Не удалось обновить корзину. Попробуйте ещё раз.'
        return [key, null] as const
      }
    }))
    if (current === revision) { products.value = Object.fromEntries(entries); loading.value = false }
  }

  const rows = computed(() => cart.items.value.map((line) => {
    const product = products.value[`${line.kind}:${line.product_id}`]
    const offer = product && !isGoods(product) ? product[line.offer] : null
    const max = product && !isGoods(product) && line.offer === 'stock' ? Math.min(99, product.stock?.qty ?? 0) : 99
    const available = Boolean(product && (isGoods(product) ? product.availability === line.offer : offer) && line.quantity <= max)
    return { line, product, available, max, price: product ? (isGoods(product) ? product.price_rub : offer?.price_rub ?? null) : null }
  }))
  const valid = computed(() => !loading.value && !error.value && rows.value.length > 0 && rows.value.every((row) => row.available))
  const total = computed(() => rows.value.some((row) => row.price === null) ? null
    : rows.value.reduce((sum, row) => sum + Number(row.price) * row.line.quantity, 0).toFixed(2))

  onMounted(() => { cart.initialize(); refresh() })
  watch(identities, refresh)
  return { rows, loading, error, valid, total, refresh }
}
