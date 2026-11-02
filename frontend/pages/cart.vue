<script setup lang="ts">
useHead({ title: 'Корзина' })
const cart = useCart()
const catalog = useCartCatalog()
function checkout() { cart.beginCheckout(); return navigateTo('/checkout/request') }
</script>

<template>
  <section>
    <h1>Корзина</h1>
    <p class="lead">Соберите заявку: менеджер уточнит наличие, комплектацию и доставку.</p>
    <p v-if="cart.storageFailed.value" class="err">Браузер не сохраняет корзину. Разрешите хранение данных для сайта, чтобы не потерять выбор при перезагрузке.</p>
    <p v-if="catalog.loading.value" role="status">Обновляем корзину…</p>
    <div v-if="catalog.error.value" class="card err" role="alert">{{ catalog.error.value }} <button type="button" @click="catalog.refresh">Повторить</button></div>
    <template v-if="cart.items.value.length">
      <CartContents v-if="!catalog.loading.value" :rows="catalog.rows.value" editable />
      <div class="card summary">
        <strong>Предварительно: {{ catalog.total.value === null ? 'Есть позиции с ценой по запросу' : rub(catalog.total.value) }}</strong>
        <p class="muted">Цены и условия подтвердит менеджер. Отправка заявки не резервирует товары.</p>
        <button type="button" :disabled="!catalog.valid.value" @click="checkout">Оставить заявку</button>
      </div>
    </template>
    <div v-else-if="!catalog.loading.value" class="card"><p>В корзине пока ничего нет.</p><NuxtLink to="/" class="btn">Выбрать товары</NuxtLink></div>
  </section>
</template>

<style scoped>
.summary { display: grid; justify-items: start; gap: .75rem; }
.summary p { margin: 0; }
</style>
