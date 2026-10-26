<script setup lang="ts">
import type { Product } from '~/composables/useApi'

definePageMeta({ fullWidth: true })

const route = useRoute()
const { data: product, error } = await useApiFetch<Product>(`/catalog/products/${route.params.slug}/`)

const missing = computed(() => error.value?.statusCode === 404)

// Иначе поиск принял бы адрес снятой модели за живую страницу.
if (import.meta.server && missing.value) setResponseStatus(useRequestEvent()!, 404)

useHead({ title: () => product.value?.title ?? 'Байк не найден' })
useSeoMeta({ description: () => product.value?.tagline || undefined })
</script>

<template>
  <div class="container product-page">
    <NuxtLink to="/" class="back">← Каталог</NuxtLink>

    <ProductDetails v-if="product" :product="product" />

    <section v-else class="missing">
      <h1>{{ missing ? 'Байк не найден' : 'Карточка не загрузилась' }}</h1>
      <p class="muted">
        {{ missing ? 'Возможно, модель сняли с продажи — посмотрите остальные в каталоге.' : 'Обновите страницу через минуту.' }}
      </p>
      <NuxtLink to="/" class="btn">В каталог</NuxtLink>
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
