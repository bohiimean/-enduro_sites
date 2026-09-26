<script setup lang="ts">
// Запрос уходит при серверном рендеринге. Если на странице видно «ok», значит
// именно SSR-контейнер достучался до Django по внутренней сети — а не браузер
// через nginx. Это и есть проверка провода на этапе 1.
const { data: health, error } = await useApiFetch<{
  status: string
  service: string
  time: string
}>('/health/')
</script>

<template>
  <section>
    <h1>Каркас поднят</h1>
    <p class="lead">
      Django, PostgreSQL, Nuxt, nginx и фоновый worker работают в одном стеке.
    </p>

    <div v-if="health" class="card ok">
      <strong>Бэкенд отвечает при SSR:</strong>
      <code>{{ health.service }} — {{ health.status }}</code>
      <span class="muted">{{ health.time }}</span>
    </div>
    <div v-else class="card err">
      <strong>Бэкенд недоступен из SSR.</strong>
      <code>{{ error?.message }}</code>
    </div>

    <h2>Что дальше</h2>
    <ol class="steps">
      <li>Каркас, модели, админка <em>— сейчас</em></li>
      <li>Сервис курсов за границей</li>
      <li>Курс на сайте</li>
      <li>Оплата QR + KYC</li>
      <li>Кабинет и заказы</li>
    </ol>
  </section>
</template>
