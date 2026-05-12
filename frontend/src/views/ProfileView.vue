<template>
  <div class="flex flex-col h-dvh bg-gray-50">
    <!-- Header -->
    <div class="bg-white px-4 py-4 shadow-sm safe-top">
      <div class="flex items-center gap-3">
        <button class="flex h-10 w-10 items-center justify-center rounded-full text-gray-600" @click="$router.push('/')">
          ←
        </button>
        <div>
          <h1 class="text-lg font-bold text-gray-900">Мои маршруты</h1>
          <p v-if="auth.user" class="text-xs text-gray-400">{{ auth.user.email }}</p>
        </div>
      </div>
    </div>

    <!-- Preferences chart -->
    <div class="px-4 pt-4">
      <PreferencesChart :scores="prefScores" />
    </div>

    <!-- Route list -->
    <div class="flex-1 overflow-y-auto px-4 py-4 space-y-3">
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
            <p class="mt-1 text-xs text-gray-300">
              {{ formatDate(route.created_at) }}
            </p>
          </div>
          <div class="flex flex-col items-end gap-2">
            <span
              class="rounded-full px-2.5 py-0.5 text-xs font-medium"
              :class="statusClass(route.status)"
            >
              {{ statusLabel(route.status) }}
            </span>
            <button
              class="flex h-8 w-8 items-center justify-center rounded-full text-red-400 hover:bg-red-50 min-h-[44px] min-w-[44px]"
              @click.stop="confirmDelete(route.id)"
            >
              🗑
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete confirm -->
    <Teleport to="body">
      <div v-if="deleteId" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
        <div class="w-full max-w-sm rounded-2xl bg-white p-6">
          <h3 class="mb-2 text-lg font-bold">Удалить маршрут?</h3>
          <p class="mb-4 text-sm text-gray-500">Это действие нельзя отменить.</p>
          <div class="flex gap-2">
            <button class="flex-1 rounded-xl border py-3 text-sm font-medium" @click="deleteId = null">Отмена</button>
            <button class="flex-1 rounded-xl bg-red-500 py-3 text-sm font-semibold text-white" @click="doDelete">Удалить</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRoutesStore } from '@/stores/routes'
import type { Route, RouteStatus } from '@/types'
import PreferencesChart from '@/components/PreferencesChart.vue'
import client from '@/api/client'

const auth = useAuthStore()
const store = useRoutesStore()
const loading = ref(true)
const deleteId = ref<string | null>(null)
const prefScores = ref<Record<string, number>>({})

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

function confirmDelete(id: string) {
  deleteId.value = id
}

async function doDelete() {
  if (!deleteId.value) return
  await store.deleteRoute(deleteId.value)
  deleteId.value = null
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
  return new Date(iso).toLocaleDateString('ru-RU', { month: 'long', day: 'numeric', year: 'numeric' })
}
</script>
