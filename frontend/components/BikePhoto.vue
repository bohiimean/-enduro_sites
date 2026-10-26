<script setup lang="ts">
// Фото байка или заглушка, пока менеджер его не загрузил.
defineProps<{ src?: string; alt: string; eager?: boolean }>()
</script>

<template>
  <img
    v-if="src"
    :src="src"
    :alt="alt"
    :loading="eager ? 'eager' : 'lazy'"
    decoding="async"
    class="bike-photo"
  >
  <div v-else class="bike-photo empty" role="img" :aria-label="`${alt} — фото скоро`">
    <svg viewBox="0 0 120 70" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="24" cy="50" r="15" /><circle cx="97" cy="50" r="16" />
      <path d="M24 50 L52 44 M97 50 L81 14 M74 11 L88 8 M8 17 L30 27 L64 25 L80 19 M80 20 L60 32 L52 44 L66 45 L70 33 M86 31 L107 28" />
    </svg>
    <span>Фото скоро</span>
  </div>
</template>

<style scoped>
/* multiply растворяет белый фон заводских фото в сером фоне вокруг. */
.bike-photo { display: block; width: 100%; height: 100%; object-fit: contain; mix-blend-mode: multiply; }
.empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: .5rem;
  color: #9ca3af; mix-blend-mode: normal;
  font: 400 11px/1 var(--display); text-transform: uppercase; letter-spacing: .1em;
}
.empty svg { width: min(45%, 9rem); }
</style>
