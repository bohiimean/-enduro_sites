<script setup lang="ts">
// Каталог переехал на главную. Старый адрес ведёт туда же, вместе с фильтрами.
definePageMeta({ redirect: (to) => ({ path: '/', query: to.query }) })
</script>

<template>
  <div />
</template>
