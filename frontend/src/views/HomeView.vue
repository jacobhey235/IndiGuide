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
        <span class="text-xl font-bold text-gray-900">IndiGuide</span>
        <div class="flex gap-2">
          <button
            v-if="auth.isAuthenticated()"
            class="rounded-full bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors"
            @click="$router.push('/profile')"
          >
            Profile
          </button>
          <button
            class="rounded-full bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors"
            @click="auth.isAuthenticated() ? auth.logout() : (showAuth = true)"
          >
            {{ auth.isAuthenticated() ? 'Sign out' : 'Sign in' }}
          </button>
        </div>
      </div>

      <!-- Post-generation: route summary + POI list -->
      <div v-if="generatedRoute" class="flex flex-col flex-1 overflow-hidden">
        <div class="px-5 py-4 border-b border-gray-100 flex-shrink-0">
          <p class="font-semibold text-gray-900">{{ generatedRoute.name }}</p>
          <p class="text-sm text-gray-500 mt-0.5">
            {{ (generatedRoute.total_distance_m / 1000).toFixed(1) }} km ·
            {{ generatedRoute.waypoints.length }} stops ·
            {{ generatedRoute.is_circular ? 'Circular' : 'One-way' }}
          </p>
          <div class="flex gap-2 mt-3">
            <button
              class="flex-1 rounded-xl bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition-colors min-h-[44px]"
              @click="startWalk"
            >
              Start walk
            </button>
            <button
              class="flex-1 rounded-xl border border-gray-200 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors min-h-[44px]"
              @click="$router.push(`/routes/${generatedRoute!.id}`)"
            >
              Details
            </button>
          </div>
          <button
            class="mt-2 w-full text-center text-sm text-gray-400 py-1 hover:text-gray-600 transition-colors"
            @click="generatedRoute = null"
          >
            Generate a new route
          </button>
        </div>

        <div class="flex-1 overflow-y-auto divide-y divide-gray-50">
          <div
            v-for="(wp, i) in sortedWaypoints"
            :key="wp.id"
            class="px-5 py-3 flex items-center gap-3"
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
                ~{{ Math.round(wp.leg_duration_s / 60) }} min walk
              </p>
            </div>
            <button
              v-if="generatedRoute.status === 'draft'"
              class="p-1.5 text-gray-300 hover:text-red-400 transition-colors flex-shrink-0"
              title="Remove"
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
              Visited
            </button>
          </div>
        </div>
      </div>

      <!-- Pre-generation: route form -->
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
      <span class="text-xl font-bold tracking-tight text-white drop-shadow">IndiGuide</span>
      <div class="flex gap-2">
        <button
          v-if="auth.isAuthenticated()"
          class="rounded-full bg-white/90 px-4 py-2 text-sm font-medium text-gray-700 shadow backdrop-blur min-h-[44px]"
          @click="$router.push('/profile')"
        >
          Profile
        </button>
        <button
          class="rounded-full bg-white/90 px-4 py-2 text-sm font-medium text-gray-700 shadow backdrop-blur min-h-[44px]"
          @click="auth.isAuthenticated() ? auth.logout() : (showAuth = true)"
        >
          {{ auth.isAuthenticated() ? 'Sign out' : 'Sign in' }}
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
          {{ generatedRoute ? 'View route options' : 'Plan a route' }}
        </span>
      </div>

      <div v-if="drawerOpen">
        <div v-if="generatedRoute" class="px-4 pb-4">
          <div class="mb-3">
            <p class="font-semibold text-gray-900">{{ generatedRoute.name }}</p>
            <p class="text-sm text-gray-500">
              {{ (generatedRoute.total_distance_m / 1000).toFixed(1) }} km ·
              {{ generatedRoute.waypoints.length }} stops ·
              {{ generatedRoute.is_circular ? 'Circular' : 'One-way' }}
            </p>
          </div>
          <div class="flex gap-2">
            <button
              class="flex-1 rounded-xl border border-gray-200 py-3 text-sm font-medium text-gray-700 min-h-[48px]"
              @click="$router.push(`/routes/${generatedRoute!.id}`)"
            >
              Details & edit
            </button>
            <button
              class="flex-1 rounded-xl bg-blue-600 py-3 text-sm font-semibold text-white min-h-[48px]"
              @click="startWalk"
            >
              Start walk
            </button>
          </div>
          <button
            class="mt-2 w-full text-center text-sm text-gray-400 py-1"
            @click="generatedRoute = null"
          >
            Generate a new route
          </button>
        </div>

        <RouteForm
          v-else
          :selected-lat="startLat"
          :selected-lon="startLon"
          :loading="routesStore.generating"
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
import { useAuthStore } from '@/stores/auth'
import { useRoutesStore } from '@/stores/routes'
import type { Route } from '@/types'

const router = useRouter()
const auth = useAuthStore()
const routesStore = useRoutesStore()
const mapRef = ref<InstanceType<typeof AppMap> | null>(null)

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

const drawerStyle = computed(() => ({
  transition: 'transform 0.3s ease-out',
  transform: drawerOpen.value ? 'translateY(0)' : 'translateY(calc(100% - 4rem))',
}))

function onHandleClick() {
  if (dragging) return
  drawerOpen.value = !drawerOpen.value
}

function onDragStart(e: MouseEvent) { dragging = false; dragStartY = e.clientY }
function onTouchStart(e: TouchEvent) { dragging = false; dragStartY = e.touches[0].clientY }

function onDragMove(e: MouseEvent) {
  if (!dragStartY) return
  if (e.clientY - dragStartY > 60) { drawerOpen.value = false; dragging = true; dragStartY = 0 }
}
function onTouchMove(e: TouchEvent) {
  if (!dragStartY) return
  if (e.touches[0].clientY - dragStartY > 60) { drawerOpen.value = false; dragging = true; dragStartY = 0 }
}
function onDragEnd() {
  dragStartY = 0
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
}

async function onGenerate(req: { distance_m: number; num_pois: number; is_circular: boolean }) {
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
    errorMsg.value = msg ?? 'Could not generate route. Please try again.'
    setTimeout(() => { errorMsg.value = '' }, 4000)
  }
}

async function startWalk() {
  if (!generatedRoute.value) return
  await routesStore.startRoute(generatedRoute.value.id)
  router.push(`/routes/${generatedRoute.value.id}/walk`)
}

async function removeWaypoint(poiXid: string) {
  if (!generatedRoute.value) return
  try {
    generatedRoute.value = await routesStore.updateRoute(generatedRoute.value.id, {
      remove_poi_xids: [poiXid],
    })
  } catch {
    errorMsg.value = 'Could not remove POI'
    setTimeout(() => { errorMsg.value = '' }, 3000)
  }
}

async function markVisited(waypointId: number) {
  if (!generatedRoute.value) return
  try {
    generatedRoute.value = await routesStore.visitWaypoint(generatedRoute.value.id, waypointId)
  } catch {
    errorMsg.value = 'Could not mark as visited'
    setTimeout(() => { errorMsg.value = '' }, 3000)
  }
}
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
