<script setup lang="ts">
const cart = useCart()
const catalog = useCartCatalog()
const route = useRoute()
const dialog = ref<HTMLDialogElement | null>(null)
let returnFocus: HTMLElement | null = null
let previousOverflow = ''
function close() { cart.close() }
async function checkout() {
  cart.beginCheckout()
  close()
  await navigateTo('/checkout/request')
}
onMounted(() => {
  returnFocus = document.activeElement as HTMLElement | null
  previousOverflow = document.documentElement.style.overflow
  document.documentElement.style.overflow = 'hidden'
  dialog.value?.showModal()
})
onBeforeUnmount(() => {
  dialog.value?.close()
  document.documentElement.style.overflow = previousOverflow
  returnFocus?.focus()
})
watch(() => route.fullPath, close)
</script>

<template>
  <Teleport to="body">
    <dialog ref="dialog" class="cart-drawer" aria-labelledby="cart-title" @cancel.prevent="close" @click="($event.target === dialog) && close()">
      <div class="drawer-content">
        <header>
          <div><p class="eyebrow">Ваша заявка</p><h2 id="cart-title">Корзина</h2></div>
          <button type="button" class="close" aria-label="Закрыть корзину" autofocus @click="close">✕</button>
        </header>
        <div class="drawer-scroll">
          <p v-if="cart.storageFailed.value" class="err" role="alert">Браузер не сохраняет корзину. Разрешите хранение данных, чтобы сохранить выбор при перезагрузке.</p>
          <p v-if="catalog.loading.value" role="status">Обновляем корзину…</p>
          <p v-if="catalog.error.value" class="err" role="alert">{{ catalog.error.value }} <button type="button" @click="catalog.refresh">Повторить</button></p>
          <template v-if="cart.items.value.length">
            <CartContents v-if="!catalog.loading.value" :rows="catalog.rows.value" editable />
            <form id="cart-checkout" @submit.prevent="checkout">
              <RequestOptions />
            </form>
          </template>
          <div v-else class="empty"><h3>Выберите свой следующий байк</h3><p class="muted">Добавьте товары из каталога — они появятся здесь.</p><button type="button" class="btn btn-outline" @click="close">Вернуться к покупкам</button></div>
        </div>
        <footer v-if="cart.items.value.length">
          <div class="total"><span>Предварительно</span><strong>{{ catalog.total.value === null ? 'Цена по запросу' : rub(catalog.total.value) }}</strong></div>
          <p class="muted">Наличие, доставку и итоговую стоимость подтвердит менеджер.</p>
          <button type="submit" form="cart-checkout" class="btn" :disabled="!catalog.valid.value">Оставить заявку →</button>
        </footer>
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
.cart-drawer { position: fixed; inset: 0 0 0 auto; margin: 0; padding: 0; width: min(100%, 36rem); max-width: 100%; height: 100dvh; max-height: 100dvh; border: 0; border-left: 1px solid var(--line); color: var(--fg); background: #fff; box-shadow: -16px 0 48px rgb(17 24 39 / .15); animation: slide-in .22s ease-out; }
.cart-drawer::backdrop { background: rgb(17 24 39 / .4); backdrop-filter: blur(3px); }
.drawer-content { height: 100%; display: flex; flex-direction: column; }
header { display: flex; align-items: center; justify-content: space-between; padding: 1.5rem; border-bottom: 1px solid var(--line); }
.eyebrow { margin: 0 0 .25rem; color: var(--accent); font: 600 .75rem/1.5 var(--display); text-transform: uppercase; letter-spacing: .12em; }
h2 { margin: 0; font: 700 2rem/1.2 var(--display); }
.close { background: var(--light); color: var(--fg); width: 2.5rem; height: 2.5rem; padding: 0; }
.drawer-scroll { flex: 1; overflow-y: auto; overscroll-behavior: contain; padding: 0 1.5rem 1.5rem; }
form { border-top: 1px solid var(--line); padding-top: 1.5rem; }
footer { padding: 1.25rem 1.5rem; border-top: 1px solid var(--line); background: var(--light); }
.total { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; }
.total strong { font: 700 1.5rem/1.3 var(--display); }
footer p { font-size: .75rem; margin: .5rem 0 1rem; }
footer .btn { width: 100%; }
.empty { padding: 2rem 0; }
.drawer-scroll :deep(.cart-line) { flex-wrap: wrap; gap: .75rem; padding: 1rem; }
.drawer-scroll :deep(.line-title) { font-size: 1.125rem; }
.drawer-scroll :deep(.line-controls) { width: 100%; grid-template-columns: 1fr 1fr; align-items: end; }
@keyframes slide-in { from { transform: translateX(100%); } }
@media (prefers-reduced-motion: reduce) { .cart-drawer { animation: none; } }
</style>
