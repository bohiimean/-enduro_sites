<script setup lang="ts">
const cart = useCart()
onMounted(async () => {
  await navigateTo('/', { replace: true })
  cart.open()
})
</script>

<template><p role="status">Открываем корзину…</p></template>
