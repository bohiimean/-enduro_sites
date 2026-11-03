<script setup lang="ts">
import type { CartLine } from '~/composables/useCart'
import type { CartRow } from '~/composables/useCartCatalog'
defineProps<{ rows: CartRow[]; editable?: boolean }>()
const cart = useCart()
const error = ref('')
function changeOffer(row: CartRow, event: Event) {
  if (!row.product) return
  error.value = cart.changeOffer(row.line, row.product, (event.target as HTMLSelectElement).value as 'stock' | 'order') ?? ''
  ;(event.target as HTMLSelectElement).value = row.line.offer
}
function setQuantity(line: CartLine, event: Event) {
  const input = event.target as HTMLInputElement
  cart.quantity(line, Number(input.value))
  if (event.type === 'change') input.value = String(line.quantity)
}
</script>

<template>
  <p v-if="error" class="err" role="alert">{{ error }}</p>
  <ul class="cart-lines">
    <li v-for="row in rows" :key="cartLineKey(row.line)" class="card cart-line">
      <div class="line-info">
        <NuxtLink v-if="row.product" :to="catalogItemPath(row.product)" class="line-title">{{ row.product.title }}</NuxtLink>
        <strong v-else>Товар недоступен</strong>
        <label v-if="editable && row.product && !isGoods(row.product)">Предложение
          <select :value="row.line.offer" @change="changeOffer(row, $event)">
            <option v-if="row.product.stock" value="stock">В наличии</option>
            <option v-if="row.product.order" value="order">Под заказ</option>
          </select>
        </label>
        <span v-else class="muted">{{ row.line.offer === 'stock' ? 'В наличии' : 'Под заказ' }}</span>
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
.line-info { display: grid; gap: .375rem; flex: 1; min-width: 0; }
.line-title { color: var(--fg); font: 700 1.25rem/1.3 var(--display); text-decoration: none; }
.line-info p { margin: 0; font-size: .8rem; }
.line-controls { display: grid; gap: .5rem; width: 7rem; }
label { font-size: .75rem; }
input, select { width: 100%; }
select { padding: .5rem; background: #fff; color: var(--fg); border: 1px solid var(--line); }
.remove { background: transparent; color: var(--muted); border: 1px solid var(--line); padding: .5rem; }
@media (max-width: 600px) {
  .cart-line { flex-wrap: wrap; gap: .75rem; }
  .line-controls { width: 100%; grid-template-columns: 1fr 1fr; align-items: end; }
}
</style>
