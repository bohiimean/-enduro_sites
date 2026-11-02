<script setup lang="ts">
/**
 * Вкладка «Заказы»: статус поставки по номеру телефона, как в боте.
 *
 * Отличие от бота — номер вводится один раз и фиксируется. Сменить его можно
 * только через менеджера: форма ниже отправляет заявку, а не ищет по новому
 * номеру.
 */
import type { Order, OrderPhone } from '~/composables/useOrders'

definePageMeta({ middleware: 'account' })
useHead({ title: 'Заказы' })

const api = useOrders()

const phone = ref<OrderPhone | null>(null)
const orders = ref<Order[]>([])
const loadError = ref('')

const input = ref('')
const formError = ref('')
const busy = ref(false)
const changing = ref(false)

onMounted(load)

async function load() {
  try {
    phone.value = await api.phone()
    orders.value = await api.orders()
    loadError.value = ''
  } catch (e) {
    loadError.value = (e as Error).message
  }
}

async function submit() {
  formError.value = ''
  busy.value = true
  try {
    phone.value = await api.setPhone(input.value)
    input.value = ''
    changing.value = false
    orders.value = await api.orders()
  } catch (e) {
    formError.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

async function cancelRequest() {
  if (!phone.value?.phone) return
  input.value = phone.value.phone
  await submit()
}

const noun = (n: number) => {
  if (n % 100 >= 11 && n % 100 <= 14) return 'заказов'
  if (n % 10 === 1) return 'заказ'
  if (n % 10 >= 2 && n % 10 <= 4) return 'заказа'
  return 'заказов'
}

const money = (value: string) => `${Number(value).toLocaleString('ru-RU')} ₽`
const day = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
</script>

<template>
  <section>
    <h1>Личный кабинет</h1>
    <AccountTabs />

    <p v-if="loadError" class="card err">{{ loadError }}</p>

    <template v-if="phone">
      <!-- Номера ещё нет: первый ввод сразу его фиксирует. -->
      <form v-if="!phone.phone" class="card narrow" @submit.prevent="submit">
        <label>
          Номер телефона, на который оформлен заказ
          <input v-model="input" type="tel" placeholder="+7 912 345-67-89" autocomplete="tel" required />
        </label>
        <p class="muted small">
          Номер закрепится за аккаунтом. Сменить его потом можно будет только через
          менеджера — проверьте, что вписываете свой.
        </p>
        <p v-if="formError" class="err">{{ formError }}</p>
        <button type="submit" :disabled="busy">{{ busy ? 'Ищем…' : 'Показать заказы' }}</button>
      </form>

      <template v-else>
        <div class="card">
          <p class="row">
            <span>Заказы по номеру <b>{{ phone.phone }}</b></span>
            <button v-if="!changing && !phone.requested_phone" class="link" type="button" @click="changing = true">
              Сменить номер
            </button>
          </p>
          <p v-if="phone.requested_phone" class="row muted">
            <span>
              Заявка на смену на <b>{{ phone.requested_phone }}</b> ждёт менеджера.
              До его решения заказы показываются по текущему номеру.
            </span>
            <button class="link" type="button" :disabled="busy" @click="cancelRequest">Отменить заявку</button>
          </p>
        </div>

        <form v-if="changing" class="card narrow" @submit.prevent="submit">
          <label>
            Новый номер
            <input v-model="input" type="tel" placeholder="+7 912 345-67-89" autocomplete="tel" required />
          </label>
          <p class="muted small">Номер сменится, когда заявку одобрит менеджер.</p>
          <p v-if="formError" class="err">{{ formError }}</p>
          <p class="row">
            <button type="submit" :disabled="busy">{{ busy ? 'Отправляем…' : 'Отправить заявку' }}</button>
            <button class="link" type="button" @click="changing = false; formError = ''">Отмена</button>
          </p>
        </form>
      </template>
    </template>

    <template v-if="phone && (phone.phone || orders.length)">
      <h2 v-if="orders.length">Найдено {{ orders.length }} {{ noun(orders.length) }}</h2>
      <p v-else class="muted">
        Заказы по этому номеру не найдены. Если заказ оформлен на другой номер —
        отправьте заявку на смену или напишите менеджеру.
      </p>

      <article v-for="order in orders" :key="order.id" class="card order">
        <header class="row">
          <h3>{{ order.title }}<template v-if="order.color"> — {{ order.color }}</template></h3>
          <span class="badge" :class="order.status_final ? 'in' : 'out'">
            {{ order.status || 'статус уточняется' }}
          </span>
        </header>
        <dl>
          <dt>ФИО</dt><dd>{{ order.full_name || '—' }}</dd>
          <dt>Телефон</dt><dd>{{ order.phone }}</dd>
          <dt>Город</dt><dd>{{ order.city || '—' }}</dd>
          <dt>ТК</dt><dd>{{ order.delivery_company || '—' }}</dd>
          <dt>Кол-во</dt><dd>{{ order.quantity }} шт.</dd>
          <dt>Цена</dt><dd>{{ money(order.price) }}</dd>
          <dt>Оплачено</dt><dd>{{ money(order.paid) }}</dd>
          <dt>Остаток</dt><dd class="price">{{ money(order.remainder) }}</dd>
          <dt>Дата заказа</dt><dd>{{ order.ordered_at ? day(order.ordered_at) : '—' }}</dd>
        </dl>
      </article>
    </template>
  </section>
</template>

<style scoped>
.row { display: flex; align-items: center; gap: .75rem; flex-wrap: wrap; margin: 0; }
.order header { justify-content: space-between; }
.order h3 { font-size: 1.1rem; margin: 0; }
dl { display: grid; grid-template-columns: max-content 1fr; gap: .25rem 1.25rem; margin: .5rem 0 0; }
dt { color: var(--muted); }
dd { margin: 0; overflow-wrap: anywhere; }
</style>
