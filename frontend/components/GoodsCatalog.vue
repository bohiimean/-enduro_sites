<script setup lang="ts">
import type { Goods, Paginated } from '~/composables/useApi'

const route = useRoute()
const apiBase = useApiBase()
const availability = computed(() => ['stock', 'order'].includes(route.query.availability as string)
  ? route.query.availability as 'stock' | 'order' : undefined)
const category = computed(() => typeof route.query.category === 'string' && /^\d{1,18}$/.test(route.query.category)
  ? route.query.category : undefined)
const { data: categories } = await useApiFetch<{ id: number; name: string }[]>('/catalog/goods-categories/')
const { data, error, status } = await useApiFetch<Paginated<Goods>>('/catalog/goods/', {
  query: { availability, category },
})

function filterLink(key: 'availability' | 'category', value?: string) {
  return { path: '/', query: { section: 'goods', availability: availability.value, category: category.value, [key]: value } }
}

const more = ref<Goods[]>([])
const loadingMore = ref(false)
const moreFailed = ref(false)
let revision = 0
watch([availability, category], () => { revision++; more.value = []; moreFailed.value = false }, { flush: 'sync' })
watch(data, () => { more.value = []; moreFailed.value = false })
const products = computed(() => [...(data.value?.results ?? []), ...more.value])
const hasMore = computed(() => products.value.length < (data.value?.count ?? 0))

async function loadMore() {
  if (loadingMore.value) return
  const current = revision
  loadingMore.value = true
  moreFailed.value = false
  try {
    const page = await $fetch<Paginated<Goods>>('/catalog/goods/', {
      baseURL: apiBase,
      query: { availability: availability.value, category: category.value, offset: products.value.length },
    })
    if (current === revision) more.value.push(...page.results)
  } catch {
    if (current === revision) moreFailed.value = true
  } finally {
    loadingMore.value = false
  }
}
</script>

<template>
  <section class="container goods-catalog" aria-labelledby="goods-title">
    <header>
      <h1 id="goods-title">Другие товары</h1>
      <p class="muted">Техника и оборудование. Комплектацию и доставку уточнит менеджер.</p>
    </header>

    <nav class="goods-filters" aria-label="Наличие товаров">
      <NuxtLink :to="filterLink('availability')" :aria-current="!availability ? 'true' : undefined">Все товары</NuxtLink>
      <NuxtLink :to="filterLink('availability', 'stock')" :aria-current="availability === 'stock' ? 'true' : undefined">В наличии</NuxtLink>
      <NuxtLink :to="filterLink('availability', 'order')" :aria-current="availability === 'order' ? 'true' : undefined">Под заказ</NuxtLink>
    </nav>
    <nav v-if="categories?.length" class="goods-filters" aria-label="Категории товаров">
      <NuxtLink :to="filterLink('category')" :aria-current="!category ? 'true' : undefined">Все категории</NuxtLink>
      <NuxtLink v-for="item in categories" :key="item.id" :to="filterLink('category', String(item.id))" :aria-current="category === String(item.id) ? 'true' : undefined">{{ item.name }}</NuxtLink>
    </nav>

    <p v-if="error" role="alert">Каталог не загрузился. Обновите страницу через минуту.</p>
    <p v-else-if="status === 'pending'" role="status">Загружаем товары…</p>
    <div v-else-if="!products.length" class="empty">
      <p>{{ availability || category ? 'Под эти условия товаров сейчас нет.' : 'Товары скоро появятся — спросите менеджера о наличии.' }}</p>
      <NuxtLink v-if="availability || category" :to="{ path: '/', query: { section: 'goods' } }" class="btn btn-outline">Показать все товары</NuxtLink>
    </div>
    <template v-else>
      <ul class="cards">
        <li v-for="product in products" :key="product.id"><ProductCard :product="product" /></li>
      </ul>
      <div v-if="hasMore" class="more">
        <button type="button" class="btn btn-outline" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? 'Загружаем…' : 'Показать ещё' }}</button>
        <p v-if="moreFailed" role="alert" class="err">Не получилось загрузить — попробуйте ещё раз.</p>
      </div>
    </template>
  </section>
</template>

<style scoped>
.goods-catalog { padding-bottom: 4rem; }
header { padding: 1rem 0; }
h1 { margin: 0; font-size: 2.25rem; }
.goods-filters { display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: 1rem; }
.goods-filters a { padding: .625rem .875rem; border: 1px solid var(--line); color: var(--muted); text-decoration: none; font: 600 .875rem/1.2 var(--display); }
.goods-filters a[aria-current] { background: var(--fg); color: #fff; border-color: var(--fg); }
.cards { display: grid; gap: 1.5rem; list-style: none; padding: 0; margin: 1.5rem 0 0; }
.more { text-align: center; margin-top: 2rem; }
.empty { padding: 2rem 0; }
@media (min-width: 640px) { .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (min-width: 1024px) { .cards { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
</style>
