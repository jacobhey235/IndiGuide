<template>
  <div class="flex flex-col h-dvh bg-gray-50">
    <!-- Map: top 45% -->
    <div class="h-[45dvh] flex-shrink-0">
      <AppMap :route="store.currentRoute" class="w-full h-full" />
    </div>

    <!-- Bottom panel -->
    <div class="flex flex-1 flex-col overflow-hidden">
      <!-- Header -->
      <div class="bg-white px-4 py-3 shadow-sm flex items-center gap-3">
        <button
          class="flex h-10 w-10 items-center justify-center rounded-full text-gray-600"
          @click="route?.status === 'completed' || route?.status === 'abandoned' ? $router.push('/') : $router.back()"
        >
          ←
        </button>
        <div class="flex-1 min-w-0">
          <h1 class="font-bold text-gray-900 truncate">{{ route?.name }}</h1>
          <p class="text-xs text-gray-500" v-if="route">
            {{ (route.total_distance_m / 1000).toFixed(1) }} км ·
            {{ route.waypoints.length }} остановок ·
            <span :class="statusColor">{{ statusLabel(route.status) }}</span>
          </p>
        </div>
        <button
          v-if="route?.status === 'draft'"
          class="text-sm font-medium"
          :class="editMode ? 'text-blue-600' : 'text-gray-500'"
          @click="editMode = !editMode"
        >
          {{ editMode ? 'Готово' : 'Изменить' }}
        </button>
      </div>

      <!-- Waypoint list -->
      <div class="flex-1 overflow-y-auto px-4 py-3 space-y-2">
        <div v-if="!route" class="flex items-center justify-center h-full text-gray-400">Загрузка…</div>

        <POICard
          v-for="(wp, i) in route?.waypoints"
          :key="wp.id"
          :waypoint="wp"
          :index="i"
          :is-last="i === (route?.waypoints.length ?? 0) - 1"
          :edit-mode="editMode"
          @tap="selectedPOI = wp.poi"
          @move-up="moveWaypoint(i, 'up')"
          @move-down="moveWaypoint(i, 'down')"
          @remove="removeWaypoint(wp.poi_xid)"
        />
      </div>

      <!-- Action buttons -->
      <div class="bg-white px-4 py-3 shadow-t flex gap-2 safe-bottom">
        <template v-if="route?.status === 'draft'">
          <button
            class="flex-1 rounded-xl bg-blue-600 py-3.5 text-sm font-semibold text-white min-h-[48px] disabled:opacity-40"
            :disabled="!route || route.waypoints.length < 2"
            @click="startWalk"
          >
            Начать прогулку
          </button>
          <button
            v-if="!route.is_saved"
            class="rounded-xl border border-blue-200 px-4 py-3.5 text-sm font-medium text-blue-600 min-h-[48px]"
            @click="saveAndViewProfile"
          >
            Сохранить
          </button>
          <button
            class="rounded-xl border border-red-200 px-4 py-3.5 text-sm font-medium text-red-500 min-h-[48px]"
            @click="deleteAndBack"
          >
            Удалить
          </button>
        </template>
        <template v-else-if="route?.status === 'active'">
          <button
            class="flex-1 rounded-xl bg-blue-600 py-3.5 text-sm font-semibold text-white min-h-[48px]"
            @click="$router.push(`/routes/${route.id}/walk`)"
          >
            Продолжить прогулку
          </button>
        </template>
        <template v-else-if="route?.status === 'completed' || route?.status === 'abandoned'">
          <button
            v-if="!route.is_saved"
            class="flex-1 rounded-xl bg-blue-600 py-3.5 text-sm font-semibold text-white min-h-[48px] disabled:opacity-40"
            :disabled="saving"
            @click="saveAndViewProfile"
          >
            {{ saving ? '…' : 'Сохранить в профиль' }}
          </button>
          <button
            v-else
            class="flex-1 rounded-xl bg-green-500 py-3.5 text-sm font-semibold text-white min-h-[48px]"
            @click="$router.push('/profile')"
          >
            В профиле
          </button>
          <button
            class="rounded-xl border border-gray-200 px-4 py-3.5 text-sm font-medium text-gray-500 min-h-[48px]"
            @click="$router.push('/')"
          >
            На главную
          </button>
        </template>
      </div>
    </div>

    <POIModal v-if="selectedPOI" :poi="selectedPOI" @close="selectedPOI = null" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppMap from '@/components/AppMap.vue'
import POICard from '@/components/POICard.vue'
import POIModal from '@/components/POIModal.vue'
import { useRoutesStore } from '@/stores/routes'
import type { POI, RouteStatus } from '@/types'

const vRoute = useRoute()
const router = useRouter()
const store = useRoutesStore()

const editMode = ref(false)
const saving = ref(false)
const selectedPOI = ref<POI | null>(null)

const route = computed(() => store.currentRoute)

const statusColor = computed(() => ({
  draft: 'text-gray-500',
  active: 'text-blue-600',
  completed: 'text-green-600',
  abandoned: 'text-orange-500',
}[route.value?.status ?? 'draft']))

function statusLabel(status: RouteStatus) {
  return {
    draft: 'черновик',
    active: 'активный',
    completed: 'завершён',
    abandoned: 'прерван',
  }[status]
}

onMounted(() => store.fetchRoute(vRoute.params.id as string))

async function startWalk() {
  if (!route.value) return
  await store.startRoute(route.value.id)
  router.push(`/routes/${route.value.id}/walk`)
}

async function saveAndViewProfile() {
  if (!route.value) return
  saving.value = true
  try {
    await store.saveRoute(route.value.id)
    router.push('/profile')
  } finally {
    saving.value = false
  }
}

async function deleteAndBack() {
  if (!route.value) return
  await store.deleteRoute(route.value.id)
  router.push('/')
}

async function moveWaypoint(index: number, direction: 'up' | 'down') {
  if (!route.value) return
  const wps = [...route.value.waypoints].sort((a, b) => a.order_index - b.order_index)
  const swap = direction === 'up' ? index - 1 : index + 1
  if (swap < 0 || swap >= wps.length) return
  const order = wps.map((w) => w.poi_xid)
  ;[order[index], order[swap]] = [order[swap], order[index]]
  await store.updateRoute(route.value.id, { waypoint_order: order })
}

async function removeWaypoint(xid: string) {
  if (!route.value) return
  await store.updateRoute(route.value.id, { remove_poi_xids: [xid] })
}
</script>
