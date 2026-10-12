<script setup lang="ts">
import type { Product } from '~/composables/useApi'

const route = useRoute()
const { data: product } = await useApiFetch<Product>(`/catalog/products/${route.params.slug}/`)

useHead({ title: () => product.value?.title ?? 'Байк' })

const rub = (value: string | null) =>
  value === null ? 'цена по запросу' : `${Number(value).toLocaleString('ru-RU')} ₽`

// Время — в московском поясе явно: страницу рендерит сервер, и без пояса
// HTML с сервера и браузер разошлись бы на три часа.
const rateNote = computed(() => {
  const rate = product.value?.rate
  if (!rate) return ''
  const price = Number(rate.price_per_cny).toLocaleString('ru-RU', { minimumFractionDigits: 2 })
  const at = new Date(rate.fetched_at).toLocaleString('ru-RU', {
    timeZone: 'Europe/Moscow', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit',
  })
  return `по курсу ${price} ₽ за юань, ${at}`
})
</script>

<template>
  <section v-if="product">
    <NuxtLink to="/catalog" class="muted">← к каталогу</NuxtLink>
    <h1>{{ product.title }}</h1>
    <p class="lead">
      {{ [product.powertrain_label, product.tagline].filter(Boolean).join(' · ') }}
    </p>

    <div v-if="product.photos.length" class="gallery">
      <img v-for="photo in product.photos" :key="photo.id" :src="photo.url" :alt="product.title">
    </div>

    <div class="offers">
      <div class="card" :class="{ ok: product.stock }">
        <span class="muted">В наличии в Москве</span>
        <template v-if="product.stock">
          <strong class="price">{{ rub(product.stock.price_rub) }}</strong>
          <span class="muted small">{{ product.stock.qty }} шт, можно забрать сразу</span>
        </template>
        <span v-else>сейчас нет</span>
      </div>
      <div v-if="product.order" class="card">
        <span class="muted">Под заказ из Китая</span>
        <strong class="price">{{ rub(product.order.price_rub) }}</strong>
        <span v-if="product.order.lead_time" class="muted small">срок поставки {{ product.order.lead_time }}</span>
        <span v-if="product.order.price_rub && rateNote" class="muted small">{{ rateNote }}</span>
      </div>
    </div>

    <dl class="specs facts">
      <template v-if="product.colors">
        <dt>Цвета</dt><dd>{{ product.colors }}</dd>
      </template>
      <template v-if="product.documents_label">
        <dt>Документы</dt><dd>{{ product.documents_label }}</dd>
      </template>
    </dl>

    <template v-for="group in product.specs" :key="group.title">
      <h2>{{ group.title }}</h2>
      <dl class="specs">
        <template v-for="item in group.items" :key="item.label">
          <dt>{{ item.label }}</dt><dd>{{ item.value }}</dd>
        </template>
      </dl>
    </template>

    <template v-if="product.description">
      <h2>Описание</h2>
      <p class="description">{{ product.description }}</p>
    </template>
  </section>
  <section v-else>
    <h1>Байк не найден</h1>
  </section>
</template>
