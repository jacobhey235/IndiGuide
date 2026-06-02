<template>
  <div
    class="relative h-dvh overflow-hidden md:flex"
    @mousemove="onDragMove"
    @mouseup="onDragEnd"
    @touchmove.passive="onTouchMove"
    @touchend="onDragEnd"
  >
    <!-- Desktop left panel (md+) -->
    <div class="hidden md:flex md:flex-col w-[380px] bg-white shadow-2xl z-10 flex-shrink-0">
      <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100 flex-shrink-0">
        <div class="flex gap-2">
          <button
            v-if="auth.isAuthenticated()"
            class="rounded-full bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors"
            @click="$router.push('/profile')"
          >
            Профиль
          </button>
          <button
            class="rounded-full bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors"
            @click="auth.isAuthenticated() ? auth.logout() : (showAuth = true)"
          >
            {{ auth.isAuthenticated() ? 'Выйти' : 'Войти' }}
          </button>
        </div>
      </div>

      <!-- Tab switcher -->
      <div class="px-4 pt-3 pb-0 flex-shrink-0">
        <div class="flex bg-gray-100 rounded-xl p-1">
          <button
            class="flex-1 py-2 text-sm font-medium rounded-lg transition-all"
            :class="activeTab === 'explore' ? 'bg-white shadow text-gray-900' : 'text-gray-500'"
            @click="activeTab = 'explore'"
          >
            Маршруты
          </button>
          <button
            class="flex-1 py-2 text-sm font-medium rounded-lg transition-all"
            :class="activeTab === 'create' ? 'bg-white shadow text-gray-900' : 'text-gray-500'"
            @click="activeTab = 'create'"
          >
            Создать
          </button>
        </div>
      </div>

      <!-- Explore tab -->
      <PublicRoutesFeed
        v-if="activeTab === 'explore'"
        class="flex-1 overflow-hidden"
        @select="onExploreSelect"
      />

      <!-- Create tab: post-generation route summary -->
      <div v-else-if="generatedRoute" class="flex flex-col flex-1 overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-100 flex-shrink-0">
          <p class="font-semibold text-gray-900">{{ generatedRoute.name }}</p>
          <p class="text-sm text-gray-500 mt-0.5">
            {{ (generatedRoute.total_distance_m / 1000).toFixed(1) }} км ·
            {{ generatedRoute.waypoints.length }} остановок
          </p>
          <button
            class="mt-3 w-full rounded-xl bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition-colors min-h-[44px]"
            @click="startWalk"
          >
            Начать прогулку
          </button>
          <button
            class="mt-2 w-full text-center text-sm text-gray-400 py-1 hover:text-gray-600 transition-colors"
            @click="generatedRoute = null"
          >
            Создать новый маршрут
          </button>
        </div>

        <div class="flex-1 overflow-y-auto divide-y divide-gray-50">
          <div
            v-for="(wp, i) in sortedWaypoints"
            :key="wp.id"
            class="px-5 py-3 flex items-center gap-2"
          >
            <div
              class="w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
              :class="wp.is_visited ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'"
            >
              {{ wp.is_visited ? '✓' : i + 1 }}
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-gray-900 truncate">{{ wp.poi.name }}</p>
              <p v-if="wp.leg_duration_s" class="text-xs text-gray-400">
                ~{{ Math.round(wp.leg_duration_s / 60) }} мин ходьбы
              </p>
            </div>
            <div v-if="generatedRoute.status === 'draft'" class="flex flex-col gap-0.5 flex-shrink-0">
              <button
                class="p-1 text-gray-300 hover:text-gray-600 transition-colors disabled:opacity-20"
                :disabled="i === 0"
                @click="moveWaypoint(i, 'up')"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"/>
                </svg>
              </button>
              <button
                class="p-1 text-gray-300 hover:text-gray-600 transition-colors disabled:opacity-20"
                :disabled="i === sortedWaypoints.length - 1"
                @click="moveWaypoint(i, 'down')"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                </svg>
              </button>
            </div>
            <button
              v-if="generatedRoute.status === 'draft'"
              class="p-1.5 text-gray-300 hover:text-red-400 transition-colors flex-shrink-0"
              title="Удалить"
              @click="removeWaypoint(wp.poi.xid)"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
            <button
              v-if="generatedRoute.status === 'active' && !wp.is_visited"
              class="text-xs font-medium text-blue-600 bg-blue-50 rounded-lg px-2 py-1 flex-shrink-0 hover:bg-blue-100 transition-colors"
              @click="markVisited(wp.id)"
            >
              Посещено
            </button>
          </div>
        </div>
      </div>

      <!-- Create tab: route form (pre-generation) -->
      <RouteForm
        v-else
        :selected-lat="startLat"
        :selected-lon="startLon"
        :loading="routesStore.generating"
        class="flex-1 overflow-y-auto"
        @generate="onGenerate"
      />
    </div>

    <!-- Map: full-screen on mobile, flex-1 on desktop -->
    <AppMap
      ref="mapRef"
      :route="generatedRoute"
      :selected-lat="startLat"
      :selected-lon="startLon"
      :clickable="true"
      class="absolute inset-0 md:relative md:inset-auto md:flex-1"
      @point-selected="onPointSelected"
    />

    <!-- Mobile top bar (hidden on desktop) -->
    <div class="absolute left-0 right-0 top-0 flex items-center justify-between px-4 py-3 safe-top md:hidden">
      <div class="flex gap-2">
        <button
          v-if="auth.isAuthenticated()"
          class="rounded-full bg-white/90 px-4 py-2 text-sm font-medium text-gray-700 shadow backdrop-blur min-h-[44px]"
          @click="$router.push('/profile')"
        >
          Профиль
        </button>
        <button
          class="rounded-full bg-white/90 px-4 py-2 text-sm font-medium text-gray-700 shadow backdrop-blur min-h-[44px]"
          @click="auth.isAuthenticated() ? auth.logout() : (showAuth = true)"
        >
          {{ auth.isAuthenticated() ? 'Выйти' : 'Войти' }}
        </button>
      </div>
    </div>

    <!-- Mobile bottom drawer (hidden on desktop) -->
    <div
      class="absolute bottom-0 left-0 right-0 rounded-t-3xl bg-white shadow-2xl safe-bottom md:hidden"
      :style="drawerStyle"
      @transitionend="onDrawerTransitionEnd"
    >
      <div
        class="flex flex-col items-center pt-2 pb-1 cursor-grab select-none"
        @click="onHandleClick"
        @mousedown="onDragStart"
        @touchstart.passive="onTouchStart"
      >
        <div class="h-1.5 w-10 rounded-full bg-gray-300" />
        <span v-if="!drawerOpen" class="mt-1.5 text-sm font-semibold text-blue-600">
          {{ activeTab === 'explore' ? 'Маршруты' : generatedRoute ? 'Показать маршрут' : 'Создать маршрут' }}
        </span>
      </div>

      <div v-if="drawerOpen" class="flex flex-col" style="max-height: 70dvh;">
        <!-- Mobile tab switcher -->
        <div class="px-4 pb-2 flex-shrink-0">
          <div class="flex bg-gray-100 rounded-xl p-1">
            <button
              class="flex-1 py-2 text-sm font-medium rounded-lg transition-all"
              :class="activeTab === 'explore' ? 'bg-white shadow text-gray-900' : 'text-gray-500'"
              @click="activeTab = 'explore'"
            >
              Маршруты
            </button>
            <button
              class="flex-1 py-2 text-sm font-medium rounded-lg transition-all"
              :class="activeTab === 'create' ? 'bg-white shadow text-gray-900' : 'text-gray-500'"
              @click="activeTab = 'create'"
            >
              Создать
            </button>
          </div>
        </div>

        <!-- Explore tab (mobile) -->
        <PublicRoutesFeed
          v-if="activeTab === 'explore'"
          class="flex-1 overflow-hidden min-h-0"
          @select="onExploreSelect"
        />

        <!-- Create tab (mobile): post-generation -->
        <div v-else-if="generatedRoute" class="flex flex-col overflow-hidden min-h-0 flex-1">
          <div class="px-4 pt-1 pb-3 border-b border-gray-100 flex-shrink-0">
            <p class="font-semibold text-gray-900">{{ generatedRoute.name }}</p>
            <p class="text-sm text-gray-500">
              {{ (generatedRoute.total_distance_m / 1000).toFixed(1) }} км ·
              {{ generatedRoute.waypoints.length }} остановок
            </p>
            <button
              class="mt-2 w-full rounded-xl bg-blue-600 py-3 text-sm font-semibold text-white min-h-[48px]"
              @click="startWalk"
            >
              Начать прогулку
            </button>
            <button
              class="mt-1.5 w-full text-center text-sm text-gray-400 py-1"
              @click="generatedRoute = null"
            >
              Создать новый маршрут
            </button>
          </div>
          <div class="flex-1 overflow-y-auto divide-y divide-gray-50 min-h-0">
            <div
              v-for="(wp, i) in sortedWaypoints"
              :key="wp.id"
              class="px-4 py-3 flex items-center gap-2"
            >
              <div
                class="w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0"
                :class="wp.is_visited ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'"
              >
                {{ wp.is_visited ? '✓' : i + 1 }}
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-gray-900 truncate">{{ wp.poi.name }}</p>
                <p v-if="wp.leg_duration_s" class="text-xs text-gray-400">
                  ~{{ Math.round(wp.leg_duration_s / 60) }} мин ходьбы
                </p>
              </div>
              <div v-if="generatedRoute.status === 'draft'" class="flex flex-col gap-0.5 flex-shrink-0">
                <button
                  class="p-1 text-gray-300 hover:text-gray-600 transition-colors disabled:opacity-20"
                  :disabled="i === 0"
                  @click="moveWaypoint(i, 'up')"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"/>
                  </svg>
                </button>
                <button
                  class="p-1 text-gray-300 hover:text-gray-600 transition-colors disabled:opacity-20"
                  :disabled="i === sortedWaypoints.length - 1"
                  @click="moveWaypoint(i, 'down')"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                  </svg>
                </button>
              </div>
              <button
                v-if="generatedRoute.status === 'draft'"
                class="p-1.5 text-gray-300 hover:text-red-400 transition-colors flex-shrink-0"
                title="Удалить"
                @click="removeWaypoint(wp.poi.xid)"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
              <button
                v-if="generatedRoute.status === 'active' && !wp.is_visited"
                class="text-xs font-medium text-blue-600 bg-blue-50 rounded-lg px-2 py-1 flex-shrink-0 hover:bg-blue-100 transition-colors"
                @click="markVisited(wp.id)"
              >
                Посещено
              </button>
            </div>
          </div>
        </div>

        <!-- Create tab (mobile): route form -->
        <RouteForm
          v-else
          :selected-lat="startLat"
          :selected-lon="startLon"
          :loading="routesStore.generating"
          class="flex-1 overflow-y-auto"
          @generate="onGenerate"
        />
      </div>
    </div>

    <!-- Error toast -->
    <Transition name="fade">
      <div
        v-if="errorMsg"
        class="absolute left-4 right-4 top-20 rounded-xl bg-red-500 px-4 py-3 text-sm text-white shadow-lg z-20"
      >
        {{ errorMsg }}
      </div>
    </Transition>

    <AuthModal v-if="showAuth" @close="showAuth = false" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppMap from '@/components/AppMap.vue'
import RouteForm from '@/components/RouteForm.vue'
import AuthModal from '@/components/AuthModal.vue'
import PublicRoutesFeed from '@/components/PublicRoutesFeed.vue'
import { useAuthStore } from '@/stores/auth'
import { useRoutesStore } from '@/stores/routes'
import type { Route } from '@/types'

const router = useRouter()
const auth = useAuthStore()
const routesStore = useRoutesStore()
const mapRef = ref<InstanceType<typeof AppMap> | null>(null)

const activeTab = ref<'explore' | 'create'>('explore')
const drawerOpen = ref(true)
const showAuth = ref(false)
const startLat = ref<number | null>(null)
const startLon = ref<number | null>(null)
const generatedRoute = ref<Route | null>(null)
const errorMsg = ref('')

onMounted(() => {
  if (!auth.isAuthenticated()) {
    showAuth.value = true
  }
})

const sortedWaypoints = computed(() => {
  if (!generatedRoute.value) return []
  return [...generatedRoute.value.waypoints].sort((a, b) => a.order_index - b.order_index)
})

// ── Drag-to-collapse (mobile) ──────────────────────────────────────────────
let dragStartY = 0
let dragging = false
let lastTouchY = 0
let lastTouchTime = 0
let swipeVelocity = 0 // px/ms, positive = downward

const isDraggingActive = ref(false)
const dragCurrentDelta = ref(0)

const drawerStyle = computed(() => {
  if (isDraggingActive.value && drawerOpen.value) {
    return {
      transition: 'none',
      transform: `translateY(${Math.max(0, dragCurrentDelta.value)}px)`,
    }
  }
  return {
    transition: 'transform 0.3s ease-out',
    transform: drawerOpen.value ? 'translateY(0)' : 'translateY(calc(100% - 4rem))',
  }
})

function onHandleClick() {
  if (dragging) return
  drawerOpen.value = !drawerOpen.value
}

function onDragStart(e: MouseEvent) {
  dragging = false
  dragStartY = e.clientY
}

function onTouchStart(e: TouchEvent) {
  dragging = false
  dragStartY = e.touches[0].clientY
  lastTouchY = dragStartY
  lastTouchTime = Date.now()
  swipeVelocity = 0
}

function onDragMove(e: MouseEvent) {
  if (!dragStartY || !drawerOpen.value) return
  const delta = e.clientY - dragStartY
  if (delta > 5) {
    isDraggingActive.value = true
    dragCurrentDelta.value = delta
  }
}

function onTouchMove(e: TouchEvent) {
  if (!dragStartY || !drawerOpen.value) return
  const currentY = e.touches[0].clientY
  const now = Date.now()

  if (now > lastTouchTime) {
    swipeVelocity = (currentY - lastTouchY) / (now - lastTouchTime)
  }
  lastTouchY = currentY
  lastTouchTime = now

  const delta = currentY - dragStartY
  if (delta > 0) {
    isDraggingActive.value = true
    dragCurrentDelta.value = delta
  }
}

function onDragEnd() {
  const delta = dragCurrentDelta.value
  const shouldClose = drawerOpen.value && (delta > 80 || swipeVelocity > 0.3)

  isDraggingActive.value = false
  dragCurrentDelta.value = 0

  if (shouldClose) {
    drawerOpen.value = false
    dragging = true
  }

  dragStartY = 0
  lastTouchY = 0
  lastTouchTime = 0
  swipeVelocity = 0
  setTimeout(() => { dragging = false }, 50)
}

function onDrawerTransitionEnd() {
  mapRef.value?.fitViewport()
}
// ──────────────────────────────────────────────────────────────────────────

function onPointSelected(lat: number, lon: number) {
  startLat.value = lat
  startLon.value = lon
  if (!drawerOpen.value) drawerOpen.value = true
  activeTab.value = 'create'
}

function onExploreSelect(id: string) {
  router.push(`/explore/${id}`)
}

async function onGenerate(req: { distance_m: number; num_pois: number; selected_categories?: string[] }) {
  if (!auth.isAuthenticated()) { showAuth.value = true; return }
  if (!startLat.value || !startLon.value) return

  errorMsg.value = ''
  try {
    generatedRoute.value = await routesStore.generateRoute({
      start_lat: startLat.value,
      start_lon: startLon.value,
      ...req,
    })
    drawerOpen.value = false
  } catch (e: unknown) {
    const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    errorMsg.value = msg ?? 'Не удалось создать маршрут. Попробуйте ещё раз.'
    setTimeout(() => { errorMsg.value = '' }, 4000)
  }
}

async function startWalk() {
  if (!generatedRoute.value) return
  await routesStore.startRoute(generatedRoute.value.id)
  router.push(`/routes/${generatedRoute.value.id}/walk`)
}

async function moveWaypoint(index: number, direction: 'up' | 'down') {
  if (!generatedRoute.value) return
  const wps = sortedWaypoints.value
  const swap = direction === 'up' ? index - 1 : index + 1
  if (swap < 0 || swap >= wps.length) return
  const order = wps.map((w) => w.poi_xid)
  ;[order[index], order[swap]] = [order[swap], order[index]]
  try {
    const updated = await routesStore.updateRoute(generatedRoute.value.id, { waypoint_order: order })
    if (updated) generatedRoute.value = updated
  } catch {
    errorMsg.value = 'Не удалось изменить порядок'
    setTimeout(() => { errorMsg.value = '' }, 3000)
  }
}

async function removeWaypoint(poiXid: string) {
  if (!generatedRoute.value) return
  try {
    const updated = await routesStore.updateRoute(generatedRoute.value.id, {
      remove_poi_xids: [poiXid],
    })
    if (!updated || updated.waypoints.length === 0) {
      generatedRoute.value = null
      drawerOpen.value = true
    } else {
      generatedRoute.value = updated
    }
  } catch {
    errorMsg.value = 'Не удалось удалить объект'
    setTimeout(() => { errorMsg.value = '' }, 3000)
  }
}

async function markVisited(waypointId: number) {
  if (!generatedRoute.value) return
  try {
    generatedRoute.value = await routesStore.visitWaypoint(generatedRoute.value.id, waypointId)
  } catch {
    errorMsg.value = 'Не удалось отметить как посещённое'
    setTimeout(() => { errorMsg.value = '' }, 3000)
  }
}
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
