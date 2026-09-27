<script setup lang="ts">
/**
 * Платёж: QR для оплаты по СБП и его статус.
 *
 * Кнопки «Я оплатил» нет — страница сама спрашивает наш API, а тот alfabit.
 * Если человек закроет вкладку, оплату досмотрит worker, и менеджер увидит её
 * в админке.
 */
import QRCode from 'qrcode'
import type { Payment } from '~/composables/usePayments'

definePageMeta({ middleware: 'account' })
useHead({ title: 'Оплата' })

const route = useRoute()
const pay = usePayments()

const payment = ref<Payment | null>(null)
const qrImage = ref('')
const error = ref('')

let timer: ReturnType<typeof setTimeout> | null = null
onBeforeUnmount(() => timer && clearTimeout(timer))
onMounted(poll)

async function poll() {
  try {
    payment.value = await pay.payment(Number(route.params.id))
    error.value = ''
  } catch (e) {
    error.value = (e as Error).message
  }
  const p = payment.value
  if (p?.qr_payload && !qrImage.value) {
    qrImage.value = await QRCode.toDataURL(p.qr_payload, { margin: 1, width: 280 })
  }
  // Пока ждём оплату — спрашиваем каждые три секунды. Банк проводит перевод
  // до нескольких минут, поэтому без ограничения по числу попыток.
  if (!p || p.status === 'created') timer = setTimeout(poll, 3000)
}

const rub = (value: string) => Number(value).toLocaleString('ru-RU', { minimumFractionDigits: 2 })
</script>

<template>
  <section class="narrow wide">
    <h1>Оплата</h1>
    <p v-if="error" class="card err">{{ error }}</p>

    <template v-if="payment">
      <div class="card">
        <span class="sum">{{ rub(payment.amount_rub) }} ₽</span>
        <span class="muted">
          {{ payment.amount_cny }} ¥ по {{ payment.price_per_cny }} ₽ · заявка {{ payment.external_payment_id }}
        </span>
      </div>

      <div v-if="payment.status === 'paid'" class="card ok">
        <strong>Оплата получена.</strong>
        <span>Менеджер свяжется с вами для выдачи юаней.</span>
      </div>

      <div v-else-if="payment.status === 'failed'" class="card err">
        <strong>Платёж не прошёл.</strong>
        <span>
          Оформите оплату заново или напишите менеджеру.
          <NuxtLink to="/account/pay">Новая оплата</NuxtLink>
        </span>
      </div>

      <template v-else>
        <div v-if="payment.qr_payload || payment.qr_url" class="card qr">
          <img v-if="qrImage" :src="qrImage" alt="QR-код для оплаты по СБП" width="280" height="280" />
          <span class="muted">Отсканируйте камерой или в приложении банка.</span>
          <a v-if="payment.qr_url" :href="payment.qr_url" target="_blank" rel="noopener">
            Открыть в приложении банка
          </a>
        </div>
        <p v-else class="card muted">Готовим реквизиты — обычно несколько секунд…</p>

        <p v-if="payment.payer_name" class="card">
          Платите с карты на имя <strong>{{ payment.payer_name }}</strong> — иначе перевод
          не пройдёт проверку.
        </p>
        <p class="muted">
          Ждём оплату, страница обновится сама. Её можно закрыть: оплата всё равно
          будет учтена и появится в кабинете.
        </p>
      </template>
    </template>
  </section>
</template>

<style scoped>
.wide { max-width: 34rem; }
.sum { font-size: 1.6rem; font-weight: 700; }
.qr { justify-items: center; text-align: center; }
.qr img { background: #fff; border-radius: .4rem; padding: .5rem; }
</style>
