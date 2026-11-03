<script setup lang="ts">
useHead({ title: 'Заявка на покупку' })
const cart = useCart()
const catalog = useCartCatalog()
const { state, session } = useAuth()
const api = usePurchaseRequests()
const name = ref('')
const phone = ref('')
const error = ref('')
const notice = ref('')
const busy = ref(false)
const ready = ref(false)

async function prepare() {
  error.value = ''
  try {
    cart.initialize()
    if (!cart.items.value.length) { ready.value = true; return }
    if (!state.value.ready) await session()
    if (!state.value.user) {
      cart.beginCheckout()
      return navigateTo({ path: '/account/signup', query: { next: '/checkout/request' } })
    }
    ready.value = true
    try {
      const contact = await api.contact()
      name.value = contact.name
      phone.value = contact.phone
    } catch { notice.value = 'Не удалось подставить контакты. Заполните их ниже.' }
  } catch { error.value = 'Не удалось проверить вход. Попробуйте ещё раз.' }
}
onMounted(prepare)

async function submit() {
  if (busy.value || !catalog.valid.value) return
  busy.value = true
  error.value = ''
  cart.beginCheckout()
  const submissionKey = cart.submissionKey.value
  const items = cart.items.value.map((i) => ({ ...i }))
  try {
    const result = await api.submit({ name: name.value.trim(), phone: phone.value.trim(), city: cart.city.value.trim(), payment_method: cart.paymentMethod.value, submission_key: submissionKey, items })
    cart.completed(submissionKey)
    await navigateTo({ path: `/account/requests/${result.id}`, query: { sent: '1' } })
  } catch (e) {
    if ((e as { statusCode?: number }).statusCode === 403 || (e as { statusCode?: number }).statusCode === 401) {
      // Сессия могла истечь, пока человек проверял состав. Корзина сохранена.
      state.value.ready = false
      await navigateTo({ path: '/account/login', query: { next: '/checkout/request' } })
    } else error.value = purchaseRequestError(e, 'Связь прервалась. Повторите отправку — дубликат не появится.')
  } finally { busy.value = false }
}
</script>

<template>
  <section>
    <h1>Заявка на покупку</h1>
    <p v-if="error" class="card err" role="alert">{{ error }} <NuxtLink to="/account/requests">Мои заявки</NuxtLink></p>
    <button v-if="!ready && error" type="button" @click="prepare">Повторить</button>
    <p v-if="!ready && !error" role="status">Проверяем вход…</p>
    <template v-if="ready">
      <p class="lead">Подтвердите состав и контакты. Менеджер свяжется с вами, чтобы согласовать покупку.</p>
      <p v-if="cart.storageFailed.value" class="err">Браузер не сохраняет корзину. Разрешите хранение данных для сайта перед перезагрузкой.</p>
      <p v-if="catalog.loading.value">Обновляем состав…</p>
      <p v-if="catalog.error.value" class="err" role="alert">{{ catalog.error.value }} <button type="button" @click="catalog.refresh">Повторить</button></p>
      <template v-if="cart.items.value.length">
        <CartContents v-if="!catalog.loading.value" :rows="catalog.rows.value" />
        <button type="button" class="btn btn-outline" @click="cart.open">Изменить корзину</button>
        <form class="card contact-form" @submit.prevent="submit">
          <p v-if="notice" class="muted">{{ notice }}</p>
          <RequestOptions :disabled="busy" />
          <label>Имя <input v-model="name" autocomplete="name" maxlength="150" required :disabled="busy"></label>
          <label>Телефон для связи <input v-model="phone" type="tel" autocomplete="tel" maxlength="32" placeholder="+7 912 345-67-89" required :disabled="busy"></label>
          <strong>Предварительно: {{ catalog.total.value === null ? 'Есть цены по запросу' : rub(catalog.total.value) }}</strong>
          <p class="muted">Окончательные цены, наличие и доставку подтвердит менеджер. Оплата и резервирование на этом шаге не требуются.</p>
          <button type="submit" :disabled="busy || !catalog.valid.value">{{ busy ? 'Отправляем…' : 'Подтвердить заявку' }}</button>
        </form>
      </template>
      <div v-else-if="!catalog.loading.value" class="card"><p>Корзина пуста.</p><NuxtLink to="/">Вернуться в каталог</NuxtLink></div>
    </template>
  </section>
</template>

<style scoped>
.contact-form { display: grid; gap: 1rem; margin-top: 1.5rem; max-width: 36rem; }
.contact-form p { margin: 0; }
</style>
