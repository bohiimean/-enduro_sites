<script setup lang="ts">
const { state, session, signup, firstError } = useAuth()

useHead({ title: 'Регистрация' })

// Вошедшему регистрация не нужна: allauth ответил бы 409 без текста.
onMounted(async () => {
  if (!state.value.ready) await session()
  if (state.value.user) return navigateTo('/account')
})

const email = ref('')
const password = ref('')
const repeat = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''

  // Второе поле проверяем на месте: allauth принимает один пароль, а опечатку
  // лучше поймать до запроса.
  if (password.value !== repeat.value) {
    error.value = 'Пароли не совпадают.'
    return
  }

  busy.value = true
  const payload = await signup(email.value.trim(), password.value)
  busy.value = false

  // При обязательном подтверждении почты удачная регистрация отвечает 401:
  // аккаунт создан, но вход ещё закрыт до кода из письма. Это не ошибка.
  if (payload.status === 401 || payload.status === 200) {
    return navigateTo('/account/verify-email')
  }

  if (payload.status === 409) {
    error.value = 'Вы уже вошли в аккаунт. Чтобы завести новый, сначала выйдите в кабинете.'
    return
  }

  error.value = firstError(payload, 'Не удалось зарегистрироваться.')
}
</script>

<template>
  <section class="narrow">
    <h1>Регистрация</h1>

    <p class="lead">
      Для входа нужны только почта и пароль. Номер телефона спросим позже — в
      сценарии оплаты, где он и нужен.
    </p>

    <form class="card" @submit.prevent="submit">
      <label>
        Почта
        <input v-model="email" type="email" autocomplete="email" required />
      </label>

      <label>
        Пароль
        <input v-model="password" type="password" autocomplete="new-password" required />
      </label>

      <label>
        Пароль ещё раз
        <input v-model="repeat" type="password" autocomplete="new-password" required />
      </label>

      <p v-if="error" class="err">{{ error }}</p>

      <button type="submit" :disabled="busy">
        {{ busy ? 'Создаём…' : 'Зарегистрироваться' }}
      </button>
    </form>

    <p class="muted">
      Уже есть аккаунт? <NuxtLink to="/account/login">Войти</NuxtLink>.
    </p>
  </section>
</template>
