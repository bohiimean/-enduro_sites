<script setup lang="ts">
import type { PurchaseRequest } from '~/composables/usePurchaseRequests'
defineProps<{ request: PurchaseRequest }>()
</script>

<template>
  <article class="card request-details">
    <div class="request-heading"><h2>Заявка №{{ request.id }}</h2><strong class="status">{{ request.status_label }}</strong></div>
    <p class="muted">{{ moscowDateTime(request.created_at) }}</p>
    <p>{{ request.name }} · {{ request.phone }}</p>
    <p v-if="request.city">Город доставки: {{ request.city }}</p>
    <p v-if="request.payment_method">Способ оплаты: {{ request.payment_method_label }}</p>
    <ul class="request-items">
      <li v-for="item in request.items" :key="item.id">
        <div><strong>{{ item.title }}</strong><span class="muted">{{ item.offer_label }} · {{ item.quantity }} шт.</span></div>
        <span>{{ rub(item.unit_price_rub) }} за шт.</span>
      </li>
    </ul>
    <strong>Предварительно: {{ purchaseRequestTotal(request) === null ? 'Есть позиции с ценой по запросу' : rub(purchaseRequestTotal(request)) }}</strong>
    <p class="muted">Цены сохранены на момент заявки. Окончательные условия согласует менеджер.</p>
  </article>
</template>

<style scoped>
.request-details { display: grid; gap: 1rem; }
.request-details p, h2 { margin: 0; }
.request-heading { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: .75rem; }
.status { color: var(--accent-ink); }
.request-items { padding: 0; list-style: none; margin: 0; }
.request-items li { display: flex; flex-wrap: wrap; justify-content: space-between; gap: .75rem; padding: 1rem 0; border-top: 1px solid var(--line); }
.request-items li div { display: grid; gap: .25rem; }
</style>
