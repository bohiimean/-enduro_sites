<template>
  <div class="shell">
    <header class="header">
      <NuxtLink to="/" class="logo">enduro</NuxtLink>
      <nav class="nav">
        <NuxtLink to="/catalog">Каталог</NuxtLink>
        <NuxtLink to="/rate">Курс</NuxtLink>
        <NuxtLink to="/account">Кабинет</NuxtLink>
      </nav>
    </header>

    <main class="main">
      <slot />
    </main>

    <footer class="footer">
      Курс, каталог, кабинет и оплата юаня.
    </footer>
  </div>
</template>
