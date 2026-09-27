<script setup lang="ts">
const { state, verifyEmailCode, resendEmailCode, firstError } = useAuth()

useHead({ title: 'Подтверждение почты' })

const code = ref('')
const error = ref('')
const notice = ref('')
const busy = ref(false)

// Сюда попадают сразу после регистрации или после попытки входа с
// неподтверждённого адреса — в обоих случаях письмо с кодом уже отправлено.
// Ожидание кода живёт в сессии Django, поэтому страница работает и после
// перезагрузки; теряется только адрес для показа.
async function submit() {
  busy.value = true
  error.value = ''
  notice.value = ''

  const payload = await verifyEmailCode(code.value)

  busy.value = false

  if (payload.status === 200) return navigateTo('/account')

  if (payload.status === 409) {
    error.value = 'Подтверждать нечего: похоже, ожидание кода истекло. Войдите заново — пришлём новый.'
    return
  }

  error.value = firstError(payload, 'Код не подошёл. Проверьте цифры из письма.')
}

async function resend() {
  busy.value = true
  error.value = ''
  notice.value = ''

  const payload = await resendEmailCode()

  busy.value = false

  if (payload.status === 200) {
    notice.value = 'Новый код отправлен.'
    return
  }

  // 409 здесь означает, что кодов на эту попытку больше не осталось (их три)
  // либо ожидание кода истекло. И то и другое лечится входом заново.
  if (payload.status === 409) {
    error.value = 'Новый код прислать уже нельзя. Войдите заново — начнём с нового кода.'
    return
  }

  error.value = firstError(
    payload,
    'Не удалось отправить код заново. Попробуйте через несколько секунд.',
  )
}
</script>

<template>
  <section class="narrow">
    <h1>Подтверждение почты</h1>

    <p class="lead">
      Код отправлен<template v-if="state.pendingEmail"> на
        <strong>{{ state.pendingEmail }}</strong></template>. Введите его здесь — и
      сразу попадёте в кабинет.
    </p>

    <form class="card" @submit.prevent="submit">
      <label>
        Код из письма
        <input
          v-model="code"
          type="text"
          inputmode="numeric"
          autocomplete="one-time-code"
          required
        />
      </label>

      <p v-if="error" class="err">{{ error }}</p>
      <p v-if="notice" class="muted">{{ notice }}</p>

      <button type="submit" :disabled="busy">
        {{ busy ? 'Проверяем…' : 'Подтвердить' }}
      </button>
    </form>

    <p class="muted">
      Код действует 15 минут. Письма нет?
      <button class="link" type="button" :disabled="busy" @click="resend">
        Прислать заново
      </button>
    </p>
  </section>
</template>
