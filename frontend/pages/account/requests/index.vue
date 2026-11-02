<script setup lang="ts">
import type { PurchaseRequest } from '~/composables/usePurchaseRequests'
definePageMeta({ middleware: 'account' })
useHead({ title: 'Заявки на покупку' })
const api = usePurchaseRequests()
const requests = ref<PurchaseRequest[]>([])
const total = ref(0)
const loading = ref(false)
const loaded = ref(false)
const error = ref('')
async function load(more = false) {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const page = await api.list(more ? requests.value.length : 0)
    requests.value = more ? [...requests.value, ...page.results] : page.results
    total.value = page.count
    loaded.value = true
  } catch (e) { error.value = purchaseRequestError(e) }
  finally { loading.value = false }
}
onMounted(() => load())
</script>

<template>
  <section>
    <h1>Личный кабинет</h1><AccountTabs />
    <h2>Заявки на покупку</h2>
    <p class="muted">Здесь заявки менеджеру. Согласованные заказы со статусами поставки находятся во вкладке «Заказы».</p>
    <p v-if="error" class="err" role="alert">{{ error }} <button type="button" @click="load()">Повторить</button></p>
    <p v-if="loading" role="status">Загружаем…</p>
    <div v-for="request in requests" :key="request.id" class="card request-card">
      <PurchaseRequestDetails :request="request" />
      <NuxtLink :to="`/account/requests/${request.id}`">Открыть заявку →</NuxtLink>
    </div>
    <div v-if="loaded && !requests.length" class="card"><p>Пока нет заявок. Выберите товары и отправьте корзину менеджеру.</p><NuxtLink to="/" class="btn">В каталог</NuxtLink></div>
    <button v-if="requests.length < total" type="button" :disabled="loading" @click="load(true)">Показать ещё</button>
  </section>
</template>

<style scoped>
.request-card { margin-bottom: 1.5rem; padding: 0; border: 0; }
.request-card > a { display: inline-block; margin: .75rem 0; }
</style>
