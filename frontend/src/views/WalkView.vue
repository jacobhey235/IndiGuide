<template>
  <div class="flex flex-col h-dvh bg-gray-900">
    <!-- Map: top portion, centered on next POI -->
    <div class="flex-1 relative">
      <AppMap :route="store.currentRoute" class="w-full h-full" ref="mapRef" />

      <!-- Top bar overlay -->
      <div class="absolute left-0 right-0 top-0 flex items-center gap-3 px-4 py-3 safe-top">
        <button
          class="flex h-10 w-10 items-center justify-center rounded-full bg-white/90 text-gray-700 shadow backdrop-blur"
          @click="$router.push(`/routes/${routeId}`)"
        >
          ←
        </button>
        <!-- Progress bar -->
        <div class="flex-1">
          <div class="mb-1 flex justify-between text-xs text-white/80">
            <span>{{ visitedCount }} из {{ totalCount }} остановок</span>
            <span>{{ Math.round(progressPct) }}%</span>
          </div>
          <div class="h-2 rounded-full bg-white/30">
            <div
              class="h-2 rounded-full bg-green-400 transition-all duration-500"
              :style="{ width: progressPct + '%' }"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom card -->
    <div class="bg-white rounded-t-3xl px-4 pt-4 pb-4 safe-bottom shadow-2xl" style="min-height: 220px;">
      <div v-if="nextWaypoint" class="mb-4">
        <!-- Walk time indicator -->
        <div v-if="nextWaypoint.leg_duration_s" class="mb-2 flex items-center gap-1.5 text-sm text-gray-400">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          ~{{ Math.ceil(nextWaypoint.leg_duration_s / 60) }} мин ходьбы
        </div>

        <h2 class="text-xl font-bold text-gray-900 mb-1">{{ nextWaypoint.poi.name }}</h2>
        <p class="text-sm text-gray-400">
          Остановка {{ nextIndex + 1 }} из {{ totalCount }}
        </p>

        <div class="mt-2 flex flex-wrap gap-1">
          <span
            v-for="kind in kindsList"
            :key="kind"
            class="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs text-blue-700"
          >
            {{ kind }}
          </span>
        </div>
      </div>

      <div v-else class="mb-4 text-center py-4">
        <p class="text-2xl font-bold text-green-600 mb-1">Маршрут завершён!</p>
        <p class="text-sm text-gray-500">Вы посетили все {{ totalCount }} остановок</p>
      </div>

      <div v-if="nextWaypoint" class="flex gap-2">
        <button
          class="flex-1 rounded-xl bg-green-500 py-4 text-base font-bold text-white min-h-[56px] shadow-lg disabled:opacity-40"
          :disabled="marking"
          @click="markVisited"
        >
          {{ marking ? '…' : 'Я на месте' }}
        </button>
        <button
          class="rounded-xl border border-gray-200 px-4 py-4 text-sm font-medium text-gray-500 min-h-[56px]"
          @click="showEndConfirm = true"
        >
          Завершить досрочно
        </button>
      </div>

      <div v-else class="flex gap-2">
        <button
          class="flex-1 rounded-xl bg-blue-600 py-4 text-base font-bold text-white min-h-[56px] disabled:opacity-40"
          :disabled="finishing"
          @click="finishRoute(true)"
        >
          {{ finishing ? '…' : 'Сохранить в профиль' }}
        </button>
        <button
          class="rounded-xl border border-gray-200 px-4 py-4 text-sm font-medium text-gray-500 min-h-[56px]"
          :disabled="finishing"
          @click="finishRoute(false)"
        >
          На главную
        </button>
      </div>

      <button
        v-if="nextWaypoint"
        class="mt-2 w-full text-center text-sm text-blue-600 py-1"
        @click="selectedPOI = nextWaypoint!.poi"
      >
        Об этом месте
      </button>
    </div>

    <!-- End confirm dialog -->
    <Teleport to="body">
      <div v-if="showEndConfirm" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
        <div class="w-full max-w-sm rounded-2xl bg-white p-6">
          <h3 class="mb-2 text-lg font-bold">Завершить прогулку?</h3>
          <p class="mb-4 text-sm text-gray-500">Маршрут будет прерван, и вы вернётесь на главную.</p>
          <div class="flex gap-2">
            <button class="flex-1 rounded-xl border py-3 text-sm font-medium text-gray-600" @click="showEndConfirm = false">Отмена</button>
            <button class="flex-1 rounded-xl bg-red-500 py-3 text-sm font-semibold text-white" @click="abandonWalk">Завершить</button>
          </div>
        </div>
      </div>
    </Teleport>

    <POIModal v-if="selectedPOI" :poi="selectedPOI" @close="selectedPOI = null" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppMap from '@/components/AppMap.vue'
import POIModal from '@/components/POIModal.vue'
import { useRoutesStore } from '@/stores/routes'
import type { POI } from '@/types'

const vRoute = useRoute()
const router = useRouter()
const store = useRoutesStore()

const marking = ref(false)
const finishing = ref(false)
const showEndConfirm = ref(false)
const selectedPOI = ref<POI | null>(null)
const mapRef = ref<InstanceType<typeof AppMap> | null>(null)

const routeId = vRoute.params.id as string

const route = computed(() => store.currentRoute)
const sortedWaypoints = computed(() =>
  [...(route.value?.waypoints ?? [])].sort((a, b) => a.order_index - b.order_index),
)
const nextWaypoint = computed(() => sortedWaypoints.value.find((w) => !w.is_visited) ?? null)
const nextIndex = computed(() => sortedWaypoints.value.indexOf(nextWaypoint.value!))
const visitedCount = computed(() => sortedWaypoints.value.filter((w) => w.is_visited).length)
const totalCount = computed(() => sortedWaypoints.value.length)
const progressPct = computed(() => totalCount.value ? (visitedCount.value / totalCount.value) * 100 : 0)
const kindsList = computed(() =>
  (nextWaypoint.value?.poi.kinds ?? '').split(',').map((k) => k.trim().replace(/_/g, ' ')).filter(Boolean).slice(0, 3),
)

onMounted(async () => {
  await store.fetchRoute(routeId)
  centerOnNext()
})

watch(nextWaypoint, centerOnNext)

function centerOnNext() {
  mapRef.value?.focusActiveLeg()
}

async function markVisited() {
  if (!nextWaypoint.value || !route.value) return
  marking.value = true
  try {
    await store.visitWaypoint(route.value.id, nextWaypoint.value.id)
  } finally {
    marking.value = false
  }
}

async function finishRoute(save: boolean) {
  if (!route.value) return
  finishing.value = true
  try {
    if (route.value.status === 'active') {
      await store.endRoute(route.value.id)
    }
    if (save && route.value) {
      await store.saveRoute(route.value.id)
      router.push('/profile')
    } else {
      router.push('/')
    }
  } finally {
    finishing.value = false
  }
}

async function abandonWalk() {
  if (!route.value) return
  showEndConfirm.value = false
  if (route.value.status === 'active') {
    await store.endRoute(route.value.id)
  }
  router.push('/')
}
</script>
