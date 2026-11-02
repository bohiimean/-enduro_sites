export default defineNuxtPlugin((nuxtApp) => {
  const cart = useCart()
  // Публичные страницы кешируются: личная корзина появляется после гидрации.
  nuxtApp.hook('app:mounted', () => cart.initialize())
})
