<script setup lang="ts">
import type { CatalogItem } from '~/composables/useApi'
const props = defineProps<{ product: CatalogItem; prefer?: 'stock' | 'order' }>()
const cart = useCart()
const selected = ref<'stock' | 'order'>(props.prefer ?? (isGoods(props.product) ? props.product.availability : props.product.stock ? 'stock' : 'order'))
const notice = ref('')
const error = ref('')
const options = computed(() => {
  const product = props.product
  return isGoods(product) ? [product.availability] : (['stock', 'order'] as const).filter((key) => product[key])
})
watch(() => props.prefer, (value) => { if (value && options.value.includes(value)) selected.value = value })
function add() {
  error.value = cart.add(props.product, selected.value)
  notice.value = error.value ? '' : 'Добавлено в корзину'
}
</script>

<template>
  <div v-if="options.length" class="add-cart">
    <label v-if="options.length > 1">Предложение
      <select v-model="selected" @change="notice = ''; error = ''">
        <option value="stock">В наличии</option><option value="order">Под заказ</option>
      </select>
    </label>
    <button type="button" class="btn" @click="add">В корзину</button>
    <p v-if="notice" class="cart-notice" role="status">{{ notice }}. <button type="button" class="open-cart" @click="cart.open">Открыть →</button></p>
    <p v-if="error" class="err" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.add-cart { width: 100%; display: grid; gap: .625rem; }
label { display: grid; gap: .25rem; font-size: .75rem; color: var(--muted); }
select { width: 100%; background: #fff; padding: .625rem; border: 1px solid var(--line); color: var(--fg); }
.btn { width: 100%; }
.open-cart { background: none; border: 0; padding: 0; color: var(--accent); font: inherit; text-decoration: underline; }
.cart-notice, .err { margin: 0; font-size: .8rem; }
</style>
