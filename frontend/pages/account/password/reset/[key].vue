<script setup lang="ts">
const route = useRoute()
const { resetPassword, firstError } = useAuth()

useHead({ title: 'Новый пароль' })

const password = ref('')
const repeat = ref('')
const error = ref('')
const busy = ref(false)
const done = ref(false)

async function submit() {
  error.value = ''

  if (password.value !== repeat.value) {
    error.value = 'Пароли не совпадают.'
    return
  }

  busy.value = true
  const payload = await resetPassword(String(route.params.key ?? ''), password.value)
  busy.value = false

  if (payload.status === 200 || payload.status === 401) {
    done.value = true
    return
  }

  error.value = firstError(
    payload,
    'Ссылка не подошла — возможно, она устарела или уже использована.',
  )
}
</script>

<template>
  <section class="narrow">
    <h1>Новый пароль</h1>

    <div v-if="done" class="card ok">
      <p>Пароль изменён.</p>
      <p><NuxtLink to="/account/login">Войти с новым паролем</NuxtLink></p>
    </div>

    <form v-else class="card" @submit.prevent="submit">
      <label>
        Новый пароль
        <input v-model="password" type="password" autocomplete="new-password" required />
      </label>

      <label>
        Ещё раз
        <input v-model="repeat" type="password" autocomplete="new-password" required />
      </label>

      <p v-if="error" class="err">{{ error }}</p>

      <button type="submit" :disabled="busy">
        {{ busy ? 'Сохраняем…' : 'Сохранить пароль' }}
      </button>
    </form>

    <p class="muted">
      Ссылка не работает? Запросите <NuxtLink to="/account/password/reset">новую</NuxtLink>.
    </p>
  </section>
</template>
