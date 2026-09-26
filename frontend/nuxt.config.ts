export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },
  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    // SSR идёт из контейнера в контейнер по внутренней сети docker.
    apiInternalBase: process.env.NUXT_API_INTERNAL_BASE || 'http://backend:8000/api/v1',
    public: {
      // Браузер ходит через nginx — адрес относительный.
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '/api/v1',
    },
  },

  // Пороутный рендеринг (CLAUDE.md, «Рендеринг: пороутно»).
  // Публичные страницы отдаём с сервера ради поиска, кабинет и оплату — нет:
  // в HTML не должно утекать ничего от авторизованного пользователя.
  routeRules: {
    // В документе у главной стоит prerender. Пока страница показывает пульс
    // бэкенда, prerender запёк бы отметку времени на момент сборки — включим,
    // когда главная станет статическим лендингом.
    '/': { ssr: true },
    // swr, а не isr: на node-server пресете Nitro это один и тот же смысл
    // «отдаём из кеша, тихо обновляем», а isr рассчитан на edge-платформы.
    '/catalog/**': { swr: 600 },
    '/rate': { ssr: true },
    '/account/**': { ssr: false },
    '/checkout/**': { ssr: false },
  },
})
