<script setup lang="ts">
import type { Goods } from '~/composables/useApi'

definePageMeta({ fullWidth: true })

const route = useRoute()
const { data: product, error } = await useApiFetch<Goods>(`/catalog/goods/${route.params.slug}/`)

const missing = computed(() => error.value?.statusCode === 404)

// Иначе поиск принял бы адрес снятой модели за живую страницу.
if (import.meta.server && missing.value) setResponseStatus(useRequestEvent()!, 404)

useHead({ title: () => product.value?.title ?? 'Товар не найден' })
useSeoMeta({ description: () => product.value?.tagline || undefined })
</script>

<template>
  <div class="container product-page">
    <NuxtLink :to="{ path: '/', query: { section: 'goods' } }" class="back">← Каталог</NuxtLink>

    <ProductDetails v-if="product" :product="product" />

    <section v-else class="missing">
      <h1>{{ missing ? 'Товар не найден' : 'Карточка не загрузилась' }}</h1>
      <p class="muted">
        {{ missing ? 'Возможно, товар сняли с продажи — посмотрите остальные товары в каталоге.' : 'Обновите страницу через минуту.' }}
      </p>
      <NuxtLink :to="{ path: '/', query: { section: 'goods' } }" class="btn">В каталог</NuxtLink>
    </section>
  </div>
</template>

<style scoped>
.product-page { padding-top: 2rem; padding-bottom: 4rem; }
.back {
  display: inline-block; margin-bottom: 1.5rem; color: var(--muted); text-decoration: none;
  font: 600 .75rem/1 var(--display); text-transform: uppercase; letter-spacing: .1em;
}
.back:hover { color: var(--accent-ink); }
.missing { display: grid; justify-items: start; gap: .5rem; padding: 2rem 0; }
.missing p { margin: 0 0 1rem; }
</style>
