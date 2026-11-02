<script setup lang="ts">
const { state, session, login, firstError } = useAuth()
const { next, authLink } = useAuthNext()
const cart = useCart()

useHead({ title: 'Вход' })

const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

onMounted(async () => {
  cart.initialize()
  // Спрашиваем сессию: заодно Django выставит csrftoken, без него вход получит 403.
  if (!state.value.ready) await session()
  // Уже вошли — форма входа не нужна. allauth повторный вход всё равно отбивает
  // 409 без текста, и человек видел бы «проверьте почту и пароль» при верных
  // данных. Сменить аккаунт — через «Выйти» в кабинете.
  if (state.value.user) return navigateTo(next.value)
})

async function submit() {
  busy.value = true
  error.value = ''

  const payload = await login(email.value.trim(), password.value)

  busy.value = false

  if (payload.status === 200) return navigateTo(next.value)

  // Вход в другой вкладке случился, пока эта была открыта.
  if (payload.status === 409) {
    await session()
    if (state.value.user) return navigateTo(next.value)
  }

  // Адрес не подтверждён: allauth на этой же попытке отправил код заново,
  // остаётся его ввести.
  if (state.value.awaitingEmailVerification) {
    return navigateTo(authLink('/account/verify-email'))
  }

  error.value = firstError(payload, 'Не удалось войти. Проверьте почту и пароль.')
}
</script>

<template>
  <section class="narrow">
    <h1>Вход</h1>

    <form class="card" @submit.prevent="submit">
      <label>
        Почта
        <input v-model="email" type="email" autocomplete="email" required />
      </label>

      <label>
        Пароль
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>

      <p v-if="error" class="err">{{ error }}</p>

      <button type="submit" :disabled="busy">
        {{ busy ? 'Проверяем…' : 'Войти' }}
      </button>
    </form>

    <p class="muted">
      Нет аккаунта? <NuxtLink :to="authLink('/account/signup')">Зарегистрируйтесь</NuxtLink>.
      Забыли пароль? <NuxtLink to="/account/password/reset">Восстановить</NuxtLink>.
    </p>
  </section>
</template>
