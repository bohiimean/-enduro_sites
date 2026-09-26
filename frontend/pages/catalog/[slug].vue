<script setup lang="ts">
import type { Product } from '~/composables/useApi'

const route = useRoute()
const { data: product } = await useApiFetch<Product>(`/catalog/products/${route.params.slug}/`)

useHead({ title: () => product.value?.title ?? 'Байк' })
</script>

<template>
  <section v-if="product">
    <NuxtLink to="/catalog" class="muted">← к каталогу</NuxtLink>
    <h1>{{ product.title }}</h1>
    <p class="muted">{{ product.color }}</p>
    <p v-if="product.price" class="price">{{ Number(product.price).toLocaleString('ru-RU') }} ₽</p>
    <p>{{ product.description }}</p>
  </section>
  <section v-else>
    <h1>Байк не найден</h1>
  </section>
</template>
