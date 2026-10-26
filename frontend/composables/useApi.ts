/**
 * Базовый адрес API зависит от того, кто спрашивает.
 *
 * При SSR запрос идёт из контейнера frontend в контейнер backend по внутренней
 * сети docker; в браузере — относительным путём через nginx. Один адрес на оба
 * случая не работает: из контейнера `/api/v1` некуда разрешить, а `backend:8000`
 * не существует для браузера.
 */
export function useApiBase(): string {
  const config = useRuntimeConfig()
  return import.meta.server ? config.apiInternalBase : config.public.apiBase
}

export function useApiFetch<T>(path: string, options: Record<string, unknown> = {}) {
  // Адрес задаётся своим $fetch, а не опцией baseURL: baseURL входит в ключ
  // кеша useFetch, а он у сервера и браузера разный. С опцией браузер не
  // находил данные, отрисованные сервером, запрашивал их заново, и Vue
  // ругался на расхождение HTML при гидрации.
  return useFetch<T>(path, { $fetch: $fetch.create({ baseURL: useApiBase() }), ...options })
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface SpecGroup {
  title: string
  items: { label: string; value: string }[]
}

/** Цены считает бэкенд по курсу; `price_rub: null` — «цена по запросу». */
export interface Product {
  id: number
  slug: string
  title: string
  brand: { id: number; name: string; slug: string }
  model: string
  model_year: number | null
  powertrain: 'ice_4t' | 'ice_2t' | 'electric'
  powertrain_label: string
  tagline: string
  description: string
  colors: string
  documents: '' | 'epts' | 'none'
  documents_label: string
  highlights: string[]
  specs: SpecGroup[]
  stock: { qty: number; price_rub: string | null } | null
  order: { price_rub: string | null; lead_time: string } | null
  rate: CatalogRate | null
  photos: { id: number; url: string; sort: number }[]
}

export interface CatalogRate {
  price_per_cny: string
  fetched_at: string
}

/** Курс юаня каталога и наценка под заказ, которую обещает главная. */
export interface CatalogTerms {
  order_markup_percent: string
  rate: CatalogRate | null
}

/** Верхняя строка сайта и главная берут один ответ: кто спросил вторым,
 * получает готовый из payload. Без этого запросов было бы два — на сервере
 * шапка и страница рендерятся по очереди, и ждать к приходу второго нечего. */
export function useCatalogTerms() {
  return useApiFetch<CatalogTerms>('/catalog/terms/', { key: 'catalog-terms', getCachedData: fromPayload })
}

function fromPayload(key: string, nuxtApp: ReturnType<typeof useNuxtApp>) {
  return nuxtApp.payload.data[key]
}

export interface Tier {
  label: string
  threshold_rub: string | null
  price_per_cny: string
}

export interface MethodPrice {
  code: string
  title: string
  subtitle: string
  note: string
  source_code: string
  available: boolean
  rate: string | null
  fetched_at: string | null
  is_stale: boolean
  tiers: Tier[]
}

export interface Showcase {
  divisor: string
  generated_at: string
  methods: MethodPrice[]
}
