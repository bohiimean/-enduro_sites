<script setup lang="ts">
import type { AccountPhone, Profile } from '~/composables/useAccount'
import type { Payment } from '~/composables/usePayments'

definePageMeta({ middleware: 'account' })

useHead({ title: 'Личный кабинет' })

const account = useAccount()
const pay = usePayments()
const payments = ref<Payment[]>([])
const { logout } = useAuth()

const profile = ref<Profile | null>(null)
const loadError = ref('')

const name = ref('')
const nameSaved = ref(false)

const newPhone = ref('')
const phoneError = ref('')
const phoneBusy = ref(false)

onMounted(load)

async function load() {
  try {
    profile.value = await account.profile()
    name.value = profile.value.full_name
    payments.value = await pay.payments()
  } catch (e) {
    loadError.value = (e as Error).message
  }
}

async function saveName() {
  nameSaved.value = false
  try {
    profile.value = await account.saveName(name.value.trim())
    nameSaved.value = true
  } catch (e) {
    loadError.value = (e as Error).message
  }
}

async function addPhone() {
  phoneError.value = ''
  phoneBusy.value = true
  try {
    await account.addPhone(newPhone.value)
    newPhone.value = ''
    await load()
  } catch (e) {
    phoneError.value = (e as Error).message
  } finally {
    phoneBusy.value = false
  }
}

async function removePhone(phone: AccountPhone) {
  phoneError.value = ''
  try {
    await account.removePhone(phone.id)
    await load()
  } catch (e) {
    phoneError.value = (e as Error).message
  }
}

async function signOut() {
  await logout()
  return navigateTo('/account/login')
}
</script>

<template>
  <section>
    <h1>Личный кабинет</h1>

    <p v-if="loadError" class="card err">{{ loadError }}</p>

    <template v-if="profile">
      <div class="card">
        <p class="row">
          <span>{{ profile.email }}</span>
          <span v-if="profile.email_verified" class="badge in">почта подтверждена</span>
          <span v-else class="badge out">почта не подтверждена</span>
        </p>
        <button class="link" type="button" @click="signOut">Выйти</button>
      </div>

      <h2>Имя</h2>
      <form class="card" @submit.prevent="saveName">
        <label>
          Как к вам обращаться
          <input v-model="name" type="text" autocomplete="name" />
        </label>
        <p v-if="nameSaved" class="muted">Сохранено.</p>
        <button type="submit">Сохранить</button>
      </form>

      <h2>Телефон</h2>
      <p class="muted">
        Номер нужен для оплаты: у alfabit верификация плательщика привязана именно к
        нему. Подтверждение номера пока не работает — каналы появятся позже, и до
        этого по номеру не открывается ни история заказов, ни данные из чужой
        верификации.
      </p>

      <ul v-if="profile.phones.length" class="phones">
        <li v-for="phone in profile.phones" :key="phone.id" class="card row">
          <span>{{ phone.phone }}</span>
          <span v-if="phone.verified" class="badge in">подтверждён</span>
          <span v-else class="badge out">не подтверждён</span>
          <button class="link" type="button" @click="removePhone(phone)">Отвязать</button>
        </li>
      </ul>
      <p v-else class="muted">Номер пока не привязан.</p>

      <form class="card" @submit.prevent="addPhone">
        <label>
          Добавить номер
          <input v-model="newPhone" type="tel" placeholder="+7 912 345-67-89" required />
        </label>
        <p v-if="phoneError" class="err">{{ phoneError }}</p>
        <button type="submit" :disabled="phoneBusy">
          {{ phoneBusy ? 'Привязываем…' : 'Привязать' }}
        </button>
      </form>

      <h2>Оплата юаня</h2>
      <p><NuxtLink to="/account/pay" class="cta">Купить юань</NuxtLink></p>
      <ul v-if="payments.length" class="phones">
        <li v-for="payment in payments" :key="payment.id">
          <NuxtLink :to="`/account/payments/${payment.id}`" class="card row plain">
            <span>{{ Number(payment.amount_rub).toLocaleString('ru-RU') }} ₽ · {{ payment.amount_cny }} ¥</span>
            <span class="badge" :class="payment.status === 'paid' ? 'in' : 'out'">
              {{ payment.status_display }}
            </span>
            <span class="muted">{{ new Date(payment.created_at).toLocaleString('ru-RU') }}</span>
          </NuxtLink>
        </li>
      </ul>

      <h2>Заказы</h2>
      <p class="muted">
        История заказов появится позже. Показывать заказы по неподтверждённому номеру
        мы не будем: он заявительный, и чужой заказ так открываться не должен.
      </p>
    </template>
  </section>
</template>

<style scoped>
.row { display: flex; align-items: center; gap: .75rem; flex-wrap: wrap; margin: 0; }
.phones { list-style: none; padding: 0; margin: 0; }
.plain { color: var(--fg); text-decoration: none; }
.plain:hover { border-color: var(--accent); }
.cta {
  display: inline-block; background: var(--accent); color: #fff;
  padding: .5rem 1rem; border-radius: .4rem; text-decoration: none;
}
</style>
