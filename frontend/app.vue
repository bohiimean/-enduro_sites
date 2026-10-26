<script setup lang="ts">
useHead({
  htmlAttrs: { lang: 'ru' },
  titleTemplate: (title) => (title ? `${title} — SKL MOTO` : 'SKL MOTO'),
})
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>
