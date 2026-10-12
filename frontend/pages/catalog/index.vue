<script setup lang="ts">
import type { Paginated, Product } from '~/composables/useApi'

const route = useRoute()

// Фильтры живут в адресе: ссылку с ними можно переслать.
const filters = {
  availability: [
    { value: undefined, label: 'Все' },
    { value: 'stock', label: 'В наличии' },
    { value: 'order', label: 'Под заказ' },
  ],
  powertrain: [
    { value: undefined, label: 'Любой тип' },
    { value: 'ice', label: 'ДВС' },
    { value: 'electric', label: 'Электро' },
  ],
} as const

type FilterKey = keyof typeof filters

const current = (key: FilterKey) => (route.query[key] as string | undefined) || undefined
const query = computed(() => ({ availability: current('availability'), powertrain: current('powertrain') }))
const linkTo = (key: FilterKey, value?: string) => ({ query: { ...route.query, [key]: value } })

const { data } = await useApiFetch<Paginated<Product>>('/catalog/products/', { query })

/** В списке одна цена: в наличии, если байк есть, иначе под заказ. */
function mainOffer(product: Product) {
  if (product.stock) {
    return { price: product.stock.price_rub, label: `в наличии, ${product.stock.qty} шт`, inStock: true }
  }
  if (product.order) return { price: product.order.price_rub, label: 'под заказ', inStock: false }
  return null
}

const cards = computed(() =>
  (data.value?.results ?? []).map((product) => ({ product, offer: mainOffer(product) })),
)
const filtered = computed(() => Boolean(query.value.availability || query.value.powertrain))

const rub = (value: string | null) =>
  value === null ? 'цена по запросу' : `${Number(value).toLocaleString('ru-RU')} ₽`

useHead({ title: 'Каталог байков' })
</script>

<template>
  <section>
    <h1>Каталог</h1>

    <nav class="filters">
      <div v-for="(options, key) in filters" :key="key">
        <NuxtLink
          v-for="option in options"
          :key="option.label"
          :to="linkTo(key, option.value)"
          :class="{ active: current(key) === option.value }"
        >
          {{ option.label }}
        </NuxtLink>
      </div>
    </nav>

    <p v-if="!cards.length" class="muted">
      <template v-if="filtered">Под эти условия байков нет.</template>
      <template v-else>Каталог пуст. Заведите байк в админке или выполните <code>make seed</code>.</template>
    </p>

    <ul v-else class="grid">
      <li v-for="{ product, offer } in cards" :key="product.id" class="card">
        <NuxtLink :to="`/catalog/${product.slug}`">
          <img v-if="product.photos.length" :src="product.photos[0].url" :alt="product.title" class="cover" loading="lazy">
          <h3>{{ product.title }}</h3>
        </NuxtLink>
        <p class="muted small">
          {{ [product.powertrain_label, ...product.highlights].join(' · ') }}
        </p>
        <p v-if="product.tagline">{{ product.tagline }}</p>
        <template v-if="offer">
          <p class="price">{{ rub(offer.price) }}</p>
          <p class="badge" :class="offer.inStock ? 'in' : 'out'">{{ offer.label }}</p>
        </template>
        <p v-else class="badge out">нет в наличии</p>
      </li>
    </ul>
  </section>
</template>
