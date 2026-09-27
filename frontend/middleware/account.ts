/**
 * Пускает в кабинет только вошедших. Работает в браузере: /account/** объявлен
 * `ssr: false`, так что на сервере эта проверка не выполняется и ничего
 * пользовательского в HTML не попадает.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  const { state, session } = useAuth()

  if (!state.value.ready) await session()

  if (!state.value.user) {
    return navigateTo({ path: '/account/login', query: { next: to.fullPath } })
  }
})
