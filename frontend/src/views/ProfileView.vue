<template>
  <div class="flex flex-col h-dvh bg-gray-50">
    <!-- Header -->
    <div class="bg-white px-4 py-4 shadow-sm safe-top">
      <div class="flex items-center gap-3">
        <button class="flex h-10 w-10 items-center justify-center rounded-full text-gray-600" @click="$router.push('/')">
          ←
        </button>
        <div>
          <h1 class="text-lg font-bold text-gray-900">Профиль</h1>
          <p v-if="auth.user" class="text-xs text-gray-400">{{ auth.user.email }}</p>
        </div>
      </div>
    </div>

    <!-- Body: sidebar + content -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Left sidebar -->
      <div class="flex flex-col w-[72px] bg-white border-r border-gray-100 py-3 gap-1 shrink-0">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="flex flex-col items-center gap-1 py-3 px-1 mx-1 rounded-xl transition-colors"
          :class="activeTab === tab.id ? 'bg-blue-50 text-blue-600' : 'text-gray-400'"
          @click="activeTab = tab.id"
        >
          <span class="text-xl leading-none">{{ tab.icon }}</span>
          <span class="text-[10px] font-medium leading-tight text-center">{{ tab.label }}</span>
        </button>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto">
        <!-- Account tab -->
        <div v-if="activeTab === 'account'" class="p-3 space-y-3">
          <!-- User info -->
          <div class="rounded-2xl bg-white p-4 shadow-sm">
            <h2 class="mb-3 text-sm font-semibold text-gray-700">Информация</h2>
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <span class="text-xs text-gray-400 w-20 shrink-0">Имя</span>
                <span class="text-sm text-gray-900">{{ auth.user?.username }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-xs text-gray-400 w-20 shrink-0">Эл. почта</span>
                <span class="text-sm text-gray-900 truncate">{{ auth.user?.email }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-xs text-gray-400 w-20 shrink-0">С нами с</span>
                <span class="text-sm text-gray-900">{{ formatDate(auth.user?.created_at ?? '') }}</span>
              </div>
            </div>
          </div>

          <!-- Interests chart -->
          <PreferencesChart :scores="prefScores" />

          <!-- Change password -->
          <div class="rounded-2xl bg-white p-4 shadow-sm">
            <button class="flex w-full items-center justify-between" @click="showPasswordForm = !showPasswordForm">
              <h2 class="text-sm font-semibold text-gray-700">Сменить пароль</h2>
              <span class="text-gray-400 text-xs">{{ showPasswordForm ? '▲' : '▼' }}</span>
            </button>
            <div v-if="showPasswordForm" class="mt-3 space-y-2.5">
              <input
                v-model="pwdCurrent"
                type="password"
                placeholder="Текущий пароль"
                class="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-blue-400"
              />
              <input
                v-model="pwdNew"
                type="password"
                placeholder="Новый пароль (мин. 8 символов)"
                class="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-blue-400"
              />
              <input
                v-model="pwdConfirm"
                type="password"
                placeholder="Повторите новый пароль"
                class="w-full rounded-xl border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-blue-400"
              />
              <p v-if="pwdError" class="text-xs text-red-500">{{ pwdError }}</p>
              <p v-if="pwdSuccess" class="text-xs text-green-600">{{ pwdSuccess }}</p>
              <button
                class="w-full rounded-xl bg-blue-600 py-3 text-sm font-semibold text-white disabled:opacity-50"
                :disabled="pwdLoading"
                @click="changePassword"
              >
                {{ pwdLoading ? 'Сохранение...' : 'Сохранить' }}
              </button>
            </div>
          </div>

          <!-- Danger zone -->
          <div class="rounded-2xl bg-white p-4 shadow-sm">
            <h2 class="mb-3 text-sm font-semibold text-gray-700">Опасная зона</h2>
            <button
              class="w-full rounded-xl border border-red-200 py-3 text-sm font-medium text-red-500 active:bg-red-50"
              @click="showDeleteConfirm = true"
            >
              Удалить аккаунт
            </button>
          </div>
        </div>

        <!-- Routes tab -->
        <div v-else-if="activeTab === 'routes'" class="p-3 space-y-3">
          <div v-if="loading" class="flex items-center justify-center py-12 text-gray-400">
            <svg class="h-6 w-6 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
            </svg>
          </div>

          <div v-else-if="store.routes.length === 0" class="flex flex-col items-center justify-center py-16 text-center">
            <p class="text-gray-400 text-sm">Нет сохранённых маршрутов.</p>
            <button class="mt-3 text-blue-600 text-sm font-medium" @click="$router.push('/')">
              Создать первый маршрут →
            </button>
          </div>

          <div
            v-for="route in store.routes"
            :key="route.id"
            class="rounded-2xl bg-white p-4 shadow-sm cursor-pointer active:bg-gray-50"
            @click="$router.push(`/routes/${route.id}`)"
          >
            <div class="flex items-start justify-between gap-2">
              <div class="flex-1 min-w-0">
                <p class="font-semibold text-gray-900 truncate">{{ route.name }}</p>
                <p class="mt-0.5 text-xs text-blue-500">
                  {{ route.author_username === auth.user?.username ? 'Вы' : route.author_username }}
                </p>
                <p class="mt-0.5 text-sm text-gray-400">
                  {{ (route.total_distance_m / 1000).toFixed(1) }} км ·
                  {{ route.waypoints.length }} остановок
                </p>
                <div class="mt-1.5 flex flex-wrap gap-1">
                  <span
                    v-for="kind in topKinds(route)"
                    :key="kind"
                    class="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-600"
                  >{{ kind }}</span>
                </div>
                <p class="mt-1 text-xs text-gray-300">{{ formatDate(route.created_at) }}</p>
              </div>
              <div class="flex flex-col items-end gap-2">
                <span
                  class="rounded-full px-2.5 py-0.5 text-xs font-medium"
                  :class="statusClass(route.status)"
                >{{ statusLabel(route.status) }}</span>
                <div class="flex items-center gap-1">
                  <button
                    v-if="!route.is_published"
                    class="rounded-full border border-green-200 px-2.5 py-1 text-xs font-medium text-green-600 hover:bg-green-50 transition-colors"
                    :disabled="publishingId === route.id"
                    @click.stop="togglePublish(route)"
                  >
                    {{ publishingId === route.id ? '…' : 'Опубликовать' }}
                  </button>
                  <button
                    v-else
                    class="rounded-full border border-gray-200 px-2.5 py-1 text-xs font-medium text-gray-500 hover:bg-gray-50 transition-colors"
                    :disabled="publishingId === route.id"
                    @click.stop="togglePublish(route)"
                  >
                    {{ publishingId === route.id ? '…' : 'Опубликован' }}
                  </button>
                  <button
                    class="flex h-8 w-8 items-center justify-center rounded-full text-red-400 hover:bg-red-50 min-h-[44px] min-w-[44px]"
                    @click.stop="confirmDeleteRoute(route.id)"
                  >
                    🗑
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete route confirm -->
    <Teleport to="body">
      <div v-if="deleteRouteId" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
        <div class="w-full max-w-sm rounded-2xl bg-white p-6">
          <h3 class="mb-2 text-lg font-bold">Удалить маршрут?</h3>
          <p class="mb-4 text-sm text-gray-500">Это действие нельзя отменить.</p>
          <p v-if="deleteRouteError" class="mb-3 text-sm text-red-500">{{ deleteRouteError }}</p>
          <div class="flex gap-2">
            <button class="flex-1 rounded-xl border py-3 text-sm font-medium" @click="deleteRouteId = null; deleteRouteError = ''">Отмена</button>
            <button class="flex-1 rounded-xl bg-red-500 py-3 text-sm font-semibold text-white" @click="doDeleteRoute">Удалить</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Delete account confirm -->
    <Teleport to="body">
      <div v-if="showDeleteConfirm" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
        <div class="w-full max-w-sm rounded-2xl bg-white p-6">
          <h3 class="mb-2 text-lg font-bold">Удалить аккаунт?</h3>
          <p class="mb-4 text-sm text-gray-500">Все ваши данные и маршруты будут удалены безвозвратно.</p>
          <div class="flex gap-2">
            <button class="flex-1 rounded-xl border py-3 text-sm font-medium" @click="showDeleteConfirm = false">Отмена</button>
            <button
              class="flex-1 rounded-xl bg-red-500 py-3 text-sm font-semibold text-white disabled:opacity-60"
              :disabled="deleteAccountLoading"
              @click="doDeleteAccount"
            >{{ deleteAccountLoading ? 'Удаление...' : 'Удалить' }}</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useRoutesStore } from '@/stores/routes'
import type { Route, RouteStatus } from '@/types'
import PreferencesChart from '@/components/PreferencesChart.vue'
import client from '@/api/client'

const router = useRouter()
const auth = useAuthStore()
const store = useRoutesStore()
const loading = ref(true)
const prefScores = ref<Record<string, number>>({})

const tabs = [
  { id: 'account' as const, icon: '👤', label: 'Аккаунт' },
  { id: 'routes' as const, icon: '🗺️', label: 'Маршруты' },
]
const activeTab = ref<'account' | 'routes'>('account')

const showPasswordForm = ref(false)
const pwdCurrent = ref('')
const pwdNew = ref('')
const pwdConfirm = ref('')
const pwdError = ref('')
const pwdSuccess = ref('')
const pwdLoading = ref(false)

const showDeleteConfirm = ref(false)
const deleteAccountLoading = ref(false)

const deleteRouteId = ref<string | null>(null)
const deleteRouteError = ref('')
const publishingId = ref<string | null>(null)

onMounted(async () => {
  const [, prefsResult] = await Promise.allSettled([
    store.fetchRoutes(),
    client.get<{ category: string; score: number }[]>('/preferences/categories'),
  ])
  if (prefsResult.status === 'fulfilled') {
    const map: Record<string, number> = {}
    for (const item of prefsResult.value.data) {
      map[item.category] = item.score
    }
    prefScores.value = map
  }
  loading.value = false
})

async function changePassword() {
  pwdError.value = ''
  pwdSuccess.value = ''
  if (pwdNew.value.length < 8) {
    pwdError.value = 'Новый пароль должен содержать минимум 8 символов'
    return
  }
  if (pwdNew.value !== pwdConfirm.value) {
    pwdError.value = 'Пароли не совпадают'
    return
  }
  pwdLoading.value = true
  try {
    await client.patch('/auth/password', { current_password: pwdCurrent.value, new_password: pwdNew.value })
    pwdSuccess.value = 'Пароль успешно изменён'
    pwdCurrent.value = ''
    pwdNew.value = ''
    pwdConfirm.value = ''
  } catch (e: any) {
    pwdError.value = e?.response?.data?.detail ?? 'Ошибка смены пароля'
  } finally {
    pwdLoading.value = false
  }
}

async function doDeleteAccount() {
  deleteAccountLoading.value = true
  try {
    await client.delete('/auth/me')
    auth.logout()
    router.push('/')
  } catch {
    showDeleteConfirm.value = false
  } finally {
    deleteAccountLoading.value = false
  }
}

async function togglePublish(route: Route) {
  publishingId.value = route.id
  try {
    if (route.is_published) {
      await store.unpublishRoute(route.id)
    } else {
      await store.publishRoute(route.id)
    }
    await store.fetchRoutes()
  } finally {
    publishingId.value = null
  }
}

function confirmDeleteRoute(id: string) {
  deleteRouteId.value = id
}

async function doDeleteRoute() {
  if (!deleteRouteId.value) return
  deleteRouteError.value = ''
  try {
    await store.deleteRoute(deleteRouteId.value)
    deleteRouteId.value = null
  } catch {
    deleteRouteError.value = 'Не удалось удалить маршрут. Попробуйте ещё раз.'
  }
}

function topKinds(route: Route): string[] {
  const counts: Record<string, number> = {}
  for (const wp of route.waypoints) {
    for (const k of (wp.poi.kinds ?? '').split(',').map((s) => s.trim()).filter(Boolean)) {
      counts[k] = (counts[k] ?? 0) + 1
    }
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([k]) => k.replace(/_/g, ' '))
}

function statusClass(status: RouteStatus) {
  return {
    draft: 'bg-gray-100 text-gray-600',
    active: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    abandoned: 'bg-orange-100 text-orange-700',
  }[status]
}

function statusLabel(status: RouteStatus) {
  return {
    draft: 'черновик',
    active: 'активный',
    completed: 'завершён',
    abandoned: 'прерван',
  }[status]
}

function formatDate(iso: string) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('ru-RU', { month: 'long', day: 'numeric', year: 'numeric' })
}
</script>
