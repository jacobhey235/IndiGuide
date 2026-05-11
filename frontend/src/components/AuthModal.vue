<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
      @click.self="$emit('close')"
    >
      <div class="w-full max-w-sm rounded-2xl bg-white p-6 shadow-2xl">
        <!-- Tabs -->
        <div class="mb-6 flex rounded-xl bg-gray-100 p-1">
          <button
            class="flex-1 rounded-lg py-2 text-sm font-medium transition-colors"
            :class="tab === 'login' ? 'bg-white shadow text-gray-900' : 'text-gray-500'"
            @click="tab = 'login'"
          >
            Войти
          </button>
          <button
            class="flex-1 rounded-lg py-2 text-sm font-medium transition-colors"
            :class="tab === 'register' ? 'bg-white shadow text-gray-900' : 'text-gray-500'"
            @click="tab = 'register'"
          >
            Регистрация
          </button>
        </div>

        <form @submit.prevent="submit" class="space-y-4">
          <div v-if="tab === 'register'">
            <label class="mb-1 block text-sm font-medium text-gray-700">Имя пользователя</label>
            <input
              v-model="form.username"
              type="text"
              class="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="Ваше имя"
              required
            />
          </div>

          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">Email</label>
            <input
              v-model="form.email"
              type="email"
              class="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="you@example.com"
              required
            />
          </div>

          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">Пароль</label>
            <input
              v-model="form.password"
              type="password"
              class="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="••••••••"
              required
              minlength="8"
            />
          </div>

          <p v-if="error" class="text-sm text-red-500">{{ error }}</p>

          <button
            type="submit"
            :disabled="loading"
            class="w-full rounded-xl bg-blue-600 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50 min-h-[48px]"
          >
            {{ loading ? 'Подождите…' : tab === 'login' ? 'Войти' : 'Создать аккаунт' }}
          </button>
        </form>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useAuthStore } from '@/stores/auth'

const emit = defineEmits<{ close: [] }>()
const auth = useAuthStore()

const tab = ref<'login' | 'register'>('login')
const loading = ref(false)
const error = ref('')
const form = reactive({ email: '', password: '', username: '' })

async function submit() {
  error.value = ''
  loading.value = true
  try {
    if (tab.value === 'login') {
      await auth.login(form.email, form.password)
    } else {
      await auth.register(form.email, form.username, form.password)
    }
    emit('close')
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    error.value = msg ?? 'Что-то пошло не так'
  } finally {
    loading.value = false
  }
}
</script>
