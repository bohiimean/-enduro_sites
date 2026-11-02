<script setup lang="ts">
import type { CartLine } from '~/composables/useCart'
import type { CartRow } from '~/composables/useCartCatalog'
defineProps<{ rows: CartRow[]; editable?: boolean }>()
const cart = useCart()
function setQuantity(line: CartLine, event: Event) {
  const input = event.target as HTMLInputElement
  cart.quantity(line, Number(input.value))
  if (event.type === 'change') input.value = String(line.quantity)
}
</script>

<template>
  <ul class="cart-lines">
    <li v-for="row in rows" :key="cartLineKey(row.line)" class="card cart-line">
      <div class="cart-image"><BikePhoto :src="row.product?.photos[0]?.url" :alt="row.product?.title ?? 'Товар'" :generic="row.line.kind === 'goods'" /></div>
      <div class="line-info">
        <NuxtLink v-if="row.product" :to="catalogItemPath(row.product)" class="line-title">{{ row.product.title }}</NuxtLink>
        <strong v-else>Товар недоступен</strong>
        <span class="muted">{{ row.line.offer === 'stock' ? 'В наличии' : 'Под заказ' }}</span>
        <span>{{ rub(row.price) }} <span class="muted">за шт.</span></span>
        <p v-if="!row.available" class="err">Предложение или количество недоступно. Измените или удалите позицию.</p>
      </div>
      <div v-if="editable" class="line-controls">
        <label>Количество
          <input :value="row.line.quantity" type="number" min="1" :max="Math.max(1, row.max)" :aria-label="`Количество: ${row.product?.title ?? 'товар'}`" @input="setQuantity(row.line, $event)" @change="setQuantity(row.line, $event)">
        </label>
        <button type="button" class="remove" @click="cart.remove(row.line)">Удалить</button>
      </div>
      <span v-else class="quantity">{{ row.line.quantity }} шт.</span>
    </li>
  </ul>
</template>

<style scoped>
.cart-lines { display: grid; gap: 1rem; padding: 0; list-style: none; }
.cart-line { display: flex; align-items: center; gap: 1.5rem; }
.cart-image { width: 7rem; height: 6rem; flex: none; }
.line-info { display: grid; gap: .375rem; flex: 1; min-width: 0; }
.line-title { color: var(--fg); font: 700 1.25rem/1.3 var(--display); text-decoration: none; }
.line-info p { margin: 0; font-size: .8rem; }
.line-controls { display: grid; gap: .5rem; width: 7rem; }
label { font-size: .75rem; }
input { width: 100%; }
.remove { background: transparent; color: var(--muted); border: 1px solid var(--line); padding: .5rem; }
@media (max-width: 600px) {
  .cart-line { flex-wrap: wrap; gap: .75rem; }
  .cart-image { width: 4rem; height: 4rem; }
  .line-controls { width: 100%; grid-template-columns: 1fr 1fr; align-items: end; }
}
</style>
