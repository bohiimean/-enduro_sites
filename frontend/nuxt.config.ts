export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },
  css: ['~/assets/css/main.css'],

  app: {
    head: {
      // Кириллица обоих шрифтов нужна на первом экране — грузим её сразу,
      // не дожидаясь разбора CSS.
      link: [
        { rel: 'preload', as: 'font', type: 'font/woff2', href: '/fonts/oswald-cyrillic.woff2', crossorigin: '' },
        { rel: 'preload', as: 'font', type: 'font/woff2', href: '/fonts/manrope-cyrillic.woff2', crossorigin: '' },
      ],
    },
  },

  runtimeConfig: {
    // SSR идёт из контейнера в контейнер по внутренней сети docker.
    apiInternalBase: process.env.NUXT_API_INTERNAL_BASE || 'http://backend:8000/api/v1',
    public: {
      // Браузер ходит через nginx — адрес относительный.
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '/api/v1',
      // Куда ведёт «Написать менеджеру» и строка Telegram в шапке — без @.
      // По умолчанию — адрес из макета.
      managerTelegram: process.env.NUXT_PUBLIC_MANAGER_TELEGRAM || 'sklmoto',
    },
  },

  // Пороутный рендеринг (CLAUDE.md, «Рендеринг: пороутно»).
  // Публичные страницы отдаём с сервера ради поиска, кабинет и оплату — нет:
  // в HTML не должно утекать ничего от авторизованного пользователя.
  routeRules: {
    // Главная — это каталог, кешируется так же. swr, а не isr: на node-server
    // пресете Nitro это один и тот же смысл «отдаём из кеша, тихо обновляем»,
    // а isr рассчитан на edge-платформы.
    '/': { swr: 600 },
    '/catalog/**': { swr: 600 },
    '/rate': { ssr: true },
    '/account/**': { ssr: false },
    '/checkout/**': { ssr: false },
  },
})
