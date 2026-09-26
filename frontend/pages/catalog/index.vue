<script setup lang="ts">
import type { Paginated, Product } from '~/composables/useApi'

const { data } = await useApiFetch<Paginated<Product>>('/catalog/products/')

useHead({ title: 'Каталог байков' })
</script>

<template>
  <section>
    <h1>Каталог</h1>

    <p v-if="!data?.results?.length" class="muted">
      Каталог пуст. Заведите байк в админке или выполните <code>make seed</code>.
    </p>

    <ul v-else class="grid">
      <li v-for="product in data.results" :key="product.id" class="card">
        <NuxtLink :to="`/catalog/${product.slug}`">
          <h3>{{ product.title }}</h3>
        </NuxtLink>
        <p class="muted">{{ product.color }}</p>
        <p v-if="product.price" class="price">{{ Number(product.price).toLocaleString('ru-RU') }} ₽</p>
        <p class="badge" :class="product.in_stock ? 'in' : 'out'">
          {{ product.in_stock ? 'в наличии' : 'под заказ' }}
        </p>
      </li>
    </ul>
  </section>
</template>
