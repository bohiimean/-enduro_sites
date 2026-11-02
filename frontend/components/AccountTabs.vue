<template>
  <nav class="tabs" aria-label="Разделы кабинета">
    <NuxtLink to="/account" exact-active-class="active">Профиль и оплата</NuxtLink>
    <NuxtLink to="/account/orders" exact-active-class="active">Заказы</NuxtLink>
  </nav>
</template>

<style scoped>
.tabs { display: flex; gap: 1.5rem; border-bottom: 1px solid var(--line); margin: 0 0 1.5rem; }
.tabs a {
  font-family: var(--display); text-transform: uppercase; font-weight: 600;
  color: var(--muted); text-decoration: none;
  padding: .5rem 0; margin-bottom: -1px; border-bottom: 3px solid transparent;
}
.tabs a:hover { color: var(--fg); }
.tabs a.active { color: var(--fg); border-bottom-color: var(--accent); }
</style>
