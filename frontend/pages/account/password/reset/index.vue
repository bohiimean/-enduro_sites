<script setup lang="ts">
const { requestPasswordReset, firstError } = useAuth()

useHead({ title: 'Восстановление пароля' })

const email = ref('')
const error = ref('')
const busy = ref(false)
const done = ref(false)

async function submit() {
  busy.value = true
  error.value = ''

  const payload = await requestPasswordReset(email.value.trim())

  busy.value = false

  // Ответ одинаковый независимо от того, есть такой аккаунт или нет: иначе по
  // форме можно проверять, кто у нас зарегистрирован.
  if (payload.status === 200 || payload.status === 401) {
    done.value = true
    return
  }

  error.value = firstError(payload, 'Не удалось отправить письмо.')
}
</script>

<template>
  <section class="narrow">
    <h1>Восстановление пароля</h1>

    <div v-if="done" class="card ok">
      <p>Если аккаунт с адресом <strong>{{ email }}</strong> существует, письмо со
        ссылкой уже отправлено.</p>
      <p class="muted">Ссылка одноразовая и живёт ограниченное время.</p>
    </div>

    <form v-else class="card" @submit.prevent="submit">
      <label>
        Почта, на которую заведён аккаунт
        <input v-model="email" type="email" autocomplete="email" required />
      </label>

      <p v-if="error" class="err">{{ error }}</p>

      <button type="submit" :disabled="busy">
        {{ busy ? 'Отправляем…' : 'Прислать ссылку' }}
      </button>
    </form>

    <p class="muted"><NuxtLink to="/account/login">Вернуться к входу</NuxtLink></p>
  </section>
</template>
