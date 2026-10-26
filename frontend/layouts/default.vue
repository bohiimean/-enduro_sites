<script setup lang="ts">
const route = useRoute()
const telegram = useRuntimeConfig().public.managerTelegram

// Цена юаня в верхней строке — та же, от которой считаются цены каталога.
const { data: terms } = useCatalogTerms()
const yuan = computed(() => (terms.value?.rate ? yuanPrice(terms.value.rate.price_per_cny) : ''))

const year = new Date().getFullYear()
</script>

<template>
  <div class="site">
    <div class="topbar">
      <div class="container topbar-row">
        <div class="topbar-group">
          <span class="live"><i class="pulse" aria-hidden="true" />Москва: выдача сегодня</span>
          <template v-if="yuan">
            <span class="sep" aria-hidden="true">|</span>
            <NuxtLink to="/rate">Курс юаня: <b>{{ yuan }}</b></NuxtLink>
          </template>
        </div>
        <a v-if="telegram" :href="`https://t.me/${telegram}`" target="_blank" rel="noopener">
          Telegram: @{{ telegram }}
        </a>
      </div>
    </div>

    <header class="header">
      <div class="container header-row">
        <NuxtLink to="/" class="logo" aria-label="SKL MOTO, на главную">
          <span class="logo-mark">SKL</span><span class="logo-word">MOTO</span>
        </NuxtLink>
        <nav class="nav">
          <NuxtLink to="/">Каталог</NuxtLink>
          <NuxtLink to="/rate">Курс юаня</NuxtLink>
        </nav>
        <NuxtLink to="/account" class="btn btn-outline cabinet">
          <span class="long">Личный кабинет</span><span class="short">Кабинет</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M17 8l4 4m0 0l-4 4m4-4H3" />
          </svg>
        </NuxtLink>
      </div>
    </header>

    <main class="main" :class="{ page: !route.meta.fullWidth }">
      <slot />
    </main>

    <footer class="footer">
      <div class="container footer-row">
        <span>© {{ year }} SKL MOTO · Москва</span>
        <nav class="footer-nav">
          <NuxtLink to="/">Каталог</NuxtLink>
          <NuxtLink to="/rate">Курс юаня</NuxtLink>
          <NuxtLink to="/account">Личный кабинет</NuxtLink>
        </nav>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.site { min-height: 100vh; display: flex; flex-direction: column; }
.main { flex: 1; width: 100%; }

.topbar {
  background: var(--light); border-bottom: 1px solid var(--line);
  font: 400 11px/1.5 var(--display); text-transform: uppercase; letter-spacing: .1em;
  color: var(--muted);
}
.topbar-row {
  display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
  gap: .25rem 1rem; padding-top: .5rem; padding-bottom: .5rem;
}
.topbar-group { display: flex; flex-wrap: wrap; align-items: center; gap: .25rem 1rem; }
.topbar a { color: inherit; text-decoration: none; transition: color .15s; }
.topbar a:hover { color: var(--accent); }
.topbar b { color: var(--accent); font-size: 14px; font-weight: 700; }
.live { display: inline-flex; align-items: center; gap: .5rem; }
.pulse { width: 8px; height: 8px; background: #10b981; animation: pulse 2s cubic-bezier(.4, 0, .6, 1) infinite; }
.sep { color: var(--line); }

@keyframes pulse { 50% { opacity: .5; } }

.header {
  position: sticky; top: 0; z-index: 40;
  background: #fff; border-bottom: 1px solid var(--line);
  box-shadow: 0 1px 2px rgb(0 0 0 / .05);
}
.header-row { height: var(--header-h); display: flex; align-items: center; gap: 2rem; }

.logo { display: flex; align-items: center; gap: .75rem; text-decoration: none; margin-right: auto; }
.logo-mark {
  background: var(--accent); color: #fff; padding: .1rem .75rem;
  font: italic 700 1.875rem/2.25rem var(--display); transform: skewX(-12deg);
}
.logo-word { font: 700 1.875rem/2.25rem var(--display); letter-spacing: .05em; color: var(--fg); }

.nav { display: flex; gap: 1.75rem; }
.nav a {
  font: 600 .875rem/1 var(--display); text-transform: uppercase; letter-spacing: .1em;
  color: var(--muted); text-decoration: none; transition: color .15s;
}
.nav a:hover, .nav a.router-link-exact-active { color: var(--accent); }

.cabinet { padding: .625rem 1.5rem; }
.cabinet svg { width: 1rem; height: 1rem; color: var(--accent); }
.cabinet .short { display: none; }

.footer { border-top: 1px solid var(--line); background: var(--light); color: var(--muted); font-size: .85rem; }
.footer-row {
  display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
  gap: .75rem 2rem; padding-top: 1.5rem; padding-bottom: 1.5rem;
}
.footer-nav { display: flex; flex-wrap: wrap; gap: .5rem 1.5rem; }
.footer-nav a { color: inherit; text-decoration: none; }
.footer-nav a:hover { color: var(--accent-ink); }

@media (max-width: 860px) {
  .nav { display: none; }
}

@media (max-width: 640px) {
  .logo-mark, .logo-word { font-size: 1.5rem; line-height: 2rem; }
  .logo { gap: .5rem; }
  .cabinet { padding: .5rem 1rem; }
  .cabinet .long { display: none; }
  .cabinet .short { display: inline; }
}
</style>
