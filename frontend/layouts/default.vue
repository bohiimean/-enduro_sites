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
      Курс и каталог работают. Личный кабинет — этап 4, оплата юаня — этап 5.
    </footer>
  </div>
</template>
