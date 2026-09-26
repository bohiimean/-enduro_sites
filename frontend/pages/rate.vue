<script setup lang="ts">
import type { Showcase } from '~/composables/useApi'

const { data, error } = await useApiFetch<Showcase>('/pricing/')

useHead({ title: 'Курс юаня' })

const moscow = new Intl.DateTimeFormat('ru-RU', {
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'Europe/Moscow',
})

function at(iso: string | null): string {
  return iso ? moscow.format(new Date(iso)) : ''
}

const available = computed(() => data.value?.methods.filter((m) => m.available) ?? [])
const unavailable = computed(() => data.value?.methods.filter((m) => !m.available) ?? [])
</script>

<template>
  <section>
    <h1>Курс юаня</h1>

    <p v-if="error" class="card err">
      Не удалось получить курс. Попробуйте обновить страницу.
    </p>

    <template v-else>
      <article v-for="method in available" :key="method.code" class="card">
        <header class="method-head">
          <h2>{{ method.title }}</h2>
          <span v-if="method.is_stale" class="stale">
            курс на {{ at(method.fetched_at) }}, обновить не удалось
          </span>
        </header>

        <p v-if="method.subtitle" class="muted">{{ method.subtitle }}</p>

        <table class="tiers">
          <tbody>
            <tr v-for="tier in method.tiers" :key="tier.label">
              <td>{{ tier.label }}</td>
              <td class="price">{{ tier.price_per_cny }} ₽</td>
            </tr>
          </tbody>
        </table>

        <p v-if="method.note" class="note">{{ method.note }}</p>
      </article>

      <p v-for="method in unavailable" :key="method.code" class="card muted">
        <strong>{{ method.title }}</strong> — курс временно недоступен.
      </p>

      <p class="muted small">
        Цена за один юань. Курс не фиксируется до момента оплаты.
      </p>
    </template>
  </section>
</template>

<style scoped>
.method-head { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
.method-head h2 { margin: 0; font-size: 1.15rem; }
.stale { color: var(--err); font-size: .85rem; }
.tiers { border-collapse: collapse; width: 100%; margin: .25rem 0; }
.tiers td { padding: .3rem 0; border-bottom: 1px solid var(--line); }
.tiers tr:last-child td { border-bottom: none; }
.tiers .price { text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }
.note { color: var(--muted); font-size: .9rem; margin: .5rem 0 0; }
.small { font-size: .9rem; }
</style>
