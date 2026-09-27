<script setup lang="ts">
const { state, session, login, firstError } = useAuth()
const route = useRoute()

useHead({ title: 'Вход' })

const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

onMounted(() => {
  // Спрашиваем сессию: заодно Django выставит csrftoken, без него вход получит 403.
  if (!state.value.ready) void session()
})

async function submit() {
  busy.value = true
  error.value = ''

  const payload = await login(email.value.trim(), password.value)

  busy.value = false

  if (payload.status === 200) {
    const next = typeof route.query.next === 'string' ? route.query.next : '/account'
    return navigateTo(next)
  }

  // Адрес не подтверждён: allauth на этой же попытке отправил код заново,
  // остаётся его ввести.
  if (state.value.awaitingEmailVerification) {
    return navigateTo('/account/verify-email')
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
      Нет аккаунта? <NuxtLink to="/account/signup">Зарегистрируйтесь</NuxtLink>.
      Забыли пароль? <NuxtLink to="/account/password/reset">Восстановить</NuxtLink>.
    </p>
  </section>
</template>
