<script setup lang="ts">
import type { RequestPaymentMethod } from '~/composables/useCart'
defineProps<{ disabled?: boolean }>()
const cart = useCart()
const city = computed({ get: () => cart.city.value, set: (value: string) => cart.setOptions(value, cart.paymentMethod.value) })
const payment = computed({ get: () => cart.paymentMethod.value, set: (value: RequestPaymentMethod) => cart.setOptions(cart.city.value, value) })
</script>

<template>
  <div class="request-options">
    <label>Город доставки
      <input v-model="city" autocomplete="address-level2" placeholder="Например, Москва" maxlength="150" required :disabled="disabled">
    </label>
    <fieldset :disabled="disabled">
      <legend>Способ оплаты</legend>
      <label v-for="option in [{ value: 'cash_moscow', label: 'Наличные в Москве' }, { value: 'sbp', label: 'СБП' }, { value: 'usdt', label: 'USDT' }]" :key="option.value" class="payment-option" :class="{ selected: payment === option.value }">
        <input v-model="payment" type="radio" :value="option.value" required>
        {{ option.label }}
      </label>
    </fieldset>
  </div>
</template>

<style scoped>
.request-options { display: grid; gap: 1.25rem; }
label { display: grid; gap: .5rem; font-size: .875rem; }
input:not([type=radio]) { width: 100%; }
fieldset { border: 0; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: .5rem; }
legend { margin-bottom: .5rem; font-size: .875rem; }
.payment-option { display: flex; align-items: center; gap: .5rem; padding: .75rem; border: 1px solid var(--line); cursor: pointer; }
.payment-option.selected { border-color: var(--accent); background: var(--light); }
input[type=radio] { width: auto; margin: 0; accent-color: var(--accent); }
</style>
