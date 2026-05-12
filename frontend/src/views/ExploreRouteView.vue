<template>
  <div class="flex flex-col h-dvh bg-gray-50">
    <!-- Map: top 45% -->
    <div class="h-[45dvh] flex-shrink-0">
      <AppMap :route="mapRoute" class="w-full h-full" />
    </div>

    <!-- Bottom panel -->
    <div class="flex flex-1 flex-col overflow-hidden">
      <!-- Header -->
      <div class="bg-white px-4 py-3 shadow-sm flex items-center gap-3">
        <button
          class="flex h-10 w-10 items-center justify-center rounded-full text-gray-600"
          @click="$router.back()"
        >
          ←
        </button>
        <div class="flex-1 min-w-0">
          <h1 class="font-bold text-gray-900 truncate">{{ route?.name ?? '…' }}</h1>
          <p class="text-xs text-gray-500" v-if="route">
            {{ (route.total_distance_m / 1000).toFixed(1) }} км ·
            {{ route.waypoints.length }} остановок ·
            <span class="text-blue-600">@{{ route.author_username }}</span>
          </p>
        </div>
      </div>

      <!-- Waypoint list -->
      <div class="flex-1 overflow-y-auto px-4 py-3 space-y-2">
        <div v-if="!route" class="flex items-center justify-center h-full text-gray-400">Загрузка…</div>

        <div
          v-for="(wp, i) in sortedWaypoints"
          :key="wp.id"
          class="flex items-center gap-3 bg-white rounded-2xl px-4 py-3 shadow-sm cursor-pointer active:bg-gray-50"
          @click="selectedPOI = wp.poi"
        >
          <div class="w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 bg-blue-100 text-blue-700">
            {{ i + 1 }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-900 truncate">{{ wp.poi.name }}</p>
            <p v-if="wp.leg_duration_s" class="text-xs text-gray-400">
              ~{{ Math.round(wp.leg_duration_s / 60) }} мин ходьбы
            </p>
          </div>
        </div>
      </div>

      <!-- Action buttons -->
      <div class="bg-white px-4 py-3 shadow-t flex gap-2 safe-bottom">
        <button
          class="flex-1 rounded-xl bg-blue-600 py-3.5 text-sm font-semibold text-white min-h-[48px] disabled:opacity-40"
          :disabled="busy"
          @click="startWalk"
        >
          {{ busy && action === 'walk' ? '…' : 'Начать прогулку' }}
        </button>
        <button
          class="rounded-xl border border-blue-200 px-4 py-3.5 text-sm font-medium text-blue-600 min-h-[48px] disabled:opacity-40"
          :disabled="busy"
          @click="saveToProfile"
        >
          {{ busy && action === 'save' ? '…' : 'Сохранить' }}
        </button>
      </div>
    </div>

    <POIModal v-if="selectedPOI" :poi="selectedPOI" @close="selectedPOI = null" />

    <!-- Error toast -->
    <Transition name="fade">
      <div
        v-if="errorMsg"
        class="absolute left-4 right-4 top-[46dvh] rounded-xl bg-red-500 px-4 py-3 text-sm text-white shadow-lg z-20"
      >
        {{ errorMsg }}
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppMap from '@/components/AppMap.vue'
import POIModal from '@/components/POIModal.vue'
import { useRoutesStore } from '@/stores/routes'
import type { POI, PublicRoute, Route } from '@/types'

const vRoute = useRoute()
const router = useRouter()
const store = useRoutesStore()

const route = ref<PublicRoute | null>(null)
const busy = ref(false)
const action = ref<'walk' | 'save' | null>(null)
const selectedPOI = ref<POI | null>(null)
const errorMsg = ref('')

const sortedWaypoints = computed(() =>
  [...(route.value?.waypoints ?? [])].sort((a, b) => a.order_index - b.order_index),
)

// AppMap expects a Route-shaped object; PublicRoute is compatible enough
const mapRoute = computed(() => route.value as unknown as Route | null)

onMounted(async () => {
  route.value = await store.fetchExploreRoute(vRoute.params.id as string)
})

function showError(msg: string) {
  errorMsg.value = msg
  setTimeout(() => { errorMsg.value = '' }, 3500)
}

async function startWalk() {
  if (!route.value) return
  busy.value = true
  action.value = 'walk'
  try {
    const cloned = await store.cloneExploreRoute(route.value.id)
    await store.startRoute(cloned.id)
    router.push(`/routes/${cloned.id}/walk`)
  } catch {
    showError('Не удалось начать прогулку')
    busy.value = false
    action.value = null
  }
}

async function saveToProfile() {
  if (!route.value) return
  busy.value = true
  action.value = 'save'
  try {
    const cloned = await store.cloneExploreRoute(route.value.id)
    await store.saveRoute(cloned.id)
    router.push('/profile')
  } catch {
    showError('Не удалось сохранить маршрут')
    busy.value = false
    action.value = null
  }
}
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
