<script setup lang="ts">
/**
 * Покупка юаня: номер → верификация → сумма. QR — на странице платежа.
 *
 * Порядок как у бота и сознательно не как в доках alfabit: верификация до
 * суммы, чтобы курс фиксировался только на время «QR → оплата», а не на всю
 * проверку документов, которая может уйти к оператору на часы.
 */
import type { AccountPhone } from '~/composables/useAccount'
import { ApiError, type KycState } from '~/composables/usePayments'

definePageMeta({ middleware: 'account' })
useHead({ title: 'Купить юань' })

const account = useAccount()
const pay = usePayments()

const phones = ref<AccountPhone[]>([])
const phoneId = ref<number | null>(null)
const newPhone = ref('')
const kyc = ref<KycState | null>(null)
const error = ref('')
const busy = ref(false)
const loaded = ref(false)

const main = ref<File | null>(null)
const registration = ref<File | null>(null)
const consent = ref(false)

const amount = ref('')
const approxPrice = ref<number | null>(null)

let timer: ReturnType<typeof setTimeout> | null = null
onBeforeUnmount(() => timer && clearTimeout(timer))

onMounted(async () => {
  try {
    phones.value = await account.phones()
    if (phones.value.length === 1) await choose(phones.value[0].id)
    loadApproxPrice()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loaded.value = true
  }
})

/** Ориентир для человека до создания платежа. Точная сумма — по свежему курсу
 *  в момент создания, её показываем на шаге QR. */
async function loadApproxPrice() {
  try {
    const showcase = await fetch('/api/v1/pricing/').then((r) => r.json())
    const method = showcase.methods?.find((m: { code: string }) => m.code === 'qr_kyc')
    const tier = method?.tiers?.[0]
    approxPrice.value = tier ? Number(tier.price_per_cny) : null
  } catch {
    approxPrice.value = null
  }
}

const approxRub = computed(() => {
  const cny = Number(amount.value.replace(',', '.'))
  if (!approxPrice.value || !cny || cny <= 0) return null
  return Math.round(cny * approxPrice.value)
})

async function addPhone() {
  error.value = ''
  busy.value = true
  try {
    const phone = await account.addPhone(newPhone.value)
    newPhone.value = ''
    phones.value = await account.phones()
    await choose(phone.id)
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

async function choose(id: number) {
  phoneId.value = id
  kyc.value = null
  await refresh()
}

/** Пока идёт распознавание, спрашиваем статус сами — кнопки «проверить» нет. */
async function refresh() {
  if (timer) clearTimeout(timer)
  if (phoneId.value === null) return
  error.value = ''
  try {
    kyc.value = await pay.kyc(phoneId.value)
  } catch (e) {
    error.value = (e as Error).message
  }
  const waiting = kyc.value?.kyc_status === 'pending' && kyc.value.processing
  if (waiting) timer = setTimeout(refresh, 4000)
}

const fileOf = (event: Event) => (event.target as HTMLInputElement).files?.[0] ?? null

async function upload() {
  if (!phoneId.value || !main.value || !registration.value) return
  error.value = ''
  busy.value = true
  try {
    kyc.value = await pay.uploadDocuments(phoneId.value, main.value, registration.value)
    main.value = null
    registration.value = null
    await refresh()
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    busy.value = false
  }
}

async function createPayment() {
  if (!phoneId.value) return
  error.value = ''
  busy.value = true
  try {
    const payment = await pay.createPayment(phoneId.value, amount.value.replace(',', '.').trim())
    return navigateTo(`/account/payments/${payment.id}`)
  } catch (e) {
    error.value = (e as Error).message
    // KYC успел смениться — показываем актуальный шаг верификации.
    if (e instanceof ApiError && e.status === 409) await refresh()
  } finally {
    busy.value = false
  }
}

const lowConfidence = computed(() => kyc.value?.documents.some((d) => d.low_confidence) ?? false)
const rub = (value: string | number) => Number(value).toLocaleString('ru-RU')
</script>

<template>
  <section class="narrow wide">
    <h1>Купить юань</h1>
    <p class="lead">
      Оплата рублями по СБП через alfabit. Перед первой оплатой — проверка паспорта:
      данные плательщика должны совпадать с данными владельца карты, с которой
      вы переводите деньги. Только для совершеннолетних.
    </p>

    <p v-if="error" class="card err">{{ error }}</p>

    <!-- Шаг 1. Номер: у alfabit верификация привязана к номеру телефона. -->
    <template v-if="loaded && phoneId === null">
      <h2>Номер плательщика</h2>
      <p class="muted">
        Номер, с которого будете платить. Верификация у alfabit привязана именно к нему.
      </p>
      <ul v-if="phones.length" class="phones">
        <li v-for="phone in phones" :key="phone.id">
          <button type="button" class="choice" @click="choose(phone.id)">{{ phone.phone }}</button>
        </li>
      </ul>
      <form class="card" @submit.prevent="addPhone">
        <label>
          {{ phones.length ? 'Или другой номер' : 'Номер телефона' }}
          <input v-model="newPhone" type="tel" placeholder="+7 912 345-67-89" required />
        </label>
        <button type="submit" :disabled="busy">Продолжить</button>
      </form>
    </template>

    <template v-else-if="kyc">
      <p class="row muted">
        Номер: {{ kyc.phone }}
        <button v-if="phones.length > 1" class="link" type="button" @click="phoneId = null; kyc = null">
          другой
        </button>
      </p>

      <!-- Шаг 2. Верификация. Три разных «ждём» звучат по-разному. -->
      <div v-if="kyc.kyc_status === 'rejected'" class="card err">
        <strong>Верификация не пройдена.</strong>
        <span>Напишите менеджеру — разберёмся, что не так с документами.</span>
      </div>

      <div v-else-if="kyc.manual_review" class="card">
        <strong>Документы проверяет сотрудник.</strong>
        <span class="muted">
          Автоматическая проверка передала заявку человеку — это дольше обычного,
          иногда несколько часов. Присылать те же фото заново не нужно. Страницу можно
          закрыть: результат появится здесь и в кабинете.
        </span>
      </div>

      <div v-else-if="kyc.kyc_status === 'pending' && kyc.processing" class="card">
        <strong>Документы на проверке.</strong>
        <span class="muted">Обычно меньше минуты. Страница обновится сама.</span>
      </div>

      <form v-else-if="kyc.can_upload" class="card" @submit.prevent="upload">
        <strong>Фото паспорта</strong>
        <span class="muted">
          Два снимка: разворот с фото и страница с пропиской. При хорошем свете, без
          бликов, края страницы в кадре. Фото не хранятся у нас — они сразу уходят в
          alfabit.
        </span>
        <p v-if="kyc.kyc_status === 'pending'" class="err">
          Проверка ждёт документы — пришлите обе страницы ещё раз.
        </p>
        <label>
          Разворот с фотографией
          <input type="file" accept="image/*,application/pdf" required @change="main = fileOf($event)" />
        </label>
        <label>
          Страница с пропиской
          <input type="file" accept="image/*,application/pdf" required @change="registration = fileOf($event)" />
        </label>
        <label class="check">
          <input v-model="consent" type="checkbox" required />
          Согласен на обработку персональных данных для проверки плательщика
        </label>
        <button type="submit" :disabled="busy || !consent || !main || !registration">
          {{ busy ? 'Отправляем…' : 'Отправить на проверку' }}
        </button>
      </form>

      <p v-if="lowConfidence && kyc.kyc_status !== 'approved'" class="card err">
        Сервис отметил, что фото читается плохо. Если проверка не пройдёт — переснимите
        страницу при хорошем свете, без бликов.
      </p>

      <!-- Шаг 3. Сумма. Курс фиксируется только в момент создания платежа. -->
      <form v-if="kyc.kyc_status === 'approved'" class="card ok" @submit.prevent="createPayment">
        <strong>Верификация пройдена.</strong>
        <span class="muted">
          Лимиты: не больше {{ rub(kyc.limits.per_operation_rub) }} ₽ за операцию и не
          больше {{ rub(kyc.limits.per_day_rub) }} ₽ за сутки по всем операциям.
        </span>
        <label>
          Сколько юаней купить
          <input v-model="amount" type="text" inputmode="decimal" placeholder="5000" required />
        </label>
        <span v-if="approxRub" class="muted">
          Около {{ rub(approxRub) }} ₽. Точная сумма — по курсу на момент оплаты, на следующем шаге.
        </span>
        <button type="submit" :disabled="busy">
          {{ busy ? 'Формируем платёж…' : 'Перейти к оплате' }}
        </button>
      </form>
    </template>

    <p v-else-if="phoneId !== null && !error" class="muted">Проверяем статус верификации…</p>
  </section>
</template>

<style scoped>
.wide { max-width: 34rem; }
.row { display: flex; align-items: center; gap: .75rem; margin: 0; }
.phones { list-style: none; padding: 0; margin: 0; display: grid; gap: .5rem; }
.choice {
  width: 100%; text-align: left; background: var(--card); color: var(--fg);
  border: 1px solid var(--line);
}
.choice:hover { border-color: var(--accent); }
.check { display: flex; gap: .5rem; align-items: flex-start; color: var(--fg); }
.check input { margin-top: .3rem; }
</style>
