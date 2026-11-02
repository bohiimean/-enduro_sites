<script setup lang="ts">
import type { PurchaseRequest } from '~/composables/usePurchaseRequests'
definePageMeta({ middleware: 'account' })
const route = useRoute()
useHead({ title: 'Заявка на покупку' })
const api = usePurchaseRequests()
const request = ref<PurchaseRequest | null>(null)
const error = ref('')
async function load() {
  error.value = ''
  try { request.value = await api.detail(String(route.params.id)) }
  catch (e) { error.value = (e as { statusCode?: number }).statusCode === 404 ? 'Заявка не найдена.' : purchaseRequestError(e) }
}
onMounted(load)
</script>

<template>
  <section>
    <h1>Личный кабинет</h1><AccountTabs />
    <div v-if="request && route.query.sent === '1'" class="card success" role="status"><strong>Заявка №{{ request.id }} принята.</strong><p>Менеджер скоро свяжется с вами по указанному телефону.</p></div>
    <PurchaseRequestDetails v-if="request" :request="request" />
    <p v-else-if="!error" role="status">Загружаем заявку…</p>
    <p v-if="error" class="err" role="alert">{{ error }} <button type="button" @click="load">Повторить</button></p>
    <NuxtLink to="/account/requests" class="back">← Все заявки</NuxtLink>
  </section>
</template>

<style scoped>
.success { margin-bottom: 1.5rem; border-color: var(--ok); }
.success p { margin-bottom: 0; }
.back { display: inline-block; margin-top: 1.5rem; }
</style>
