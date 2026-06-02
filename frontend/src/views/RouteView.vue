<template>
  <div class="flex flex-col h-dvh bg-gray-50">
    <!-- Map: top 45% -->
    <div class="h-[45dvh] flex-shrink-0">
      <AppMap :route="store.currentRoute" :clickable="true" class="w-full h-full" @point-selected="onMapTap" />
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
          v-if="hasOpeningHours"
          class="flex-shrink-0 rounded-full p-2 transition-colors"
          :class="showOpeningHours ? 'text-blue-600' : 'text-gray-300'"
          :title="showOpeningHours ? 'Скрыть часы работы' : 'Показать часы работы'"
          @click="showOpeningHours = !showOpeningHours"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
        </button>
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

        <!-- Add-point controls (edit mode only) -->
        <template v-if="editMode && route?.status === 'draft'">
          <button
            v-if="!addPointMode"
            class="w-full rounded-xl border border-dashed border-blue-300 py-2.5 text-sm text-blue-500"
            @click="addPointMode = true"
          >
            + Добавить точку
          </button>
          <div
            v-else-if="!suggesting && !suggestedPOI && !addError"
            class="rounded-xl bg-blue-50 border border-blue-200 px-4 py-3 text-sm text-blue-700 flex justify-between items-center"
          >
            <span>Нажмите на карту, чтобы выбрать место</span>
            <button class="text-blue-400 font-medium ml-3" @click="cancelAdd">Отмена</button>
          </div>
          <div
            v-else-if="suggesting"
            class="rounded-xl bg-gray-50 border border-gray-200 px-4 py-3 text-sm text-gray-500"
          >
            Ищем ближайшее место…
          </div>
          <div
            v-else-if="addError"
            class="rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-600 flex justify-between items-center"
          >
            <span>{{ addError }}</span>
            <button class="text-red-400 ml-3" @click="cancelAdd">Закрыть</button>
          </div>
          <div
            v-else-if="suggestedPOI"
            class="rounded-xl bg-white border border-green-300 shadow-sm px-4 py-3"
          >
            <p class="text-xs text-gray-400 mb-0.5">Найдено поблизости</p>
            <p class="font-semibold text-gray-900">{{ suggestedPOI.name }}</p>
            <p class="text-xs text-gray-500 mt-0.5">{{ suggestedPOI.kinds.split(',')[0] }}</p>
            <div class="flex gap-2 mt-3">
              <button
                class="flex-1 rounded-lg bg-blue-600 py-2 text-sm font-medium text-white"
                @click="confirmAdd"
              >
                Добавить
              </button>
              <button
                class="rounded-lg border border-gray-200 px-4 py-2 text-sm text-gray-500"
                @click="cancelAdd"
              >
                Отмена
              </button>
            </div>
          </div>
        </template>

        <POICard
          v-for="(wp, i) in route?.waypoints"
          :key="wp.id"
          :waypoint="wp"
          :index="i"
          :is-last="i === (route?.waypoints.length ?? 0) - 1"
          :edit-mode="editMode"
          :show-opening-hours="showOpeningHours"
          @tap="() => { selectedPOI = wp.poi; selectedIsOpen = wp.is_open ?? null }"
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
            v-if="route.is_saved && !route.is_published"
            class="rounded-xl border border-green-200 px-4 py-3.5 text-sm font-medium text-green-600 min-h-[48px] disabled:opacity-40"
            :disabled="publishing"
            @click="togglePublish"
          >
            {{ publishing ? '…' : 'Опубликовать' }}
          </button>
          <button
            v-if="route.is_saved && route.is_published"
            class="rounded-xl border border-gray-200 px-4 py-3.5 text-sm font-medium text-gray-500 min-h-[48px] disabled:opacity-40"
            :disabled="publishing"
            @click="togglePublish"
          >
            {{ publishing ? '…' : 'Снять с публикации' }}
          </button>
          <button
            v-if="!route.is_saved"
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
          <template v-else>
            <button
              class="flex-1 rounded-xl bg-green-500 py-3.5 text-sm font-semibold text-white min-h-[48px]"
              @click="$router.push('/profile')"
            >
              В профиле
            </button>
            <button
              v-if="!route.is_published"
              class="rounded-xl border border-green-200 px-4 py-3.5 text-sm font-medium text-green-600 min-h-[48px] disabled:opacity-40"
              :disabled="publishing"
              @click="togglePublish"
            >
              {{ publishing ? '…' : 'Опубликовать' }}
            </button>
            <button
              v-else
              class="rounded-xl border border-gray-200 px-4 py-3.5 text-sm font-medium text-gray-500 min-h-[48px] disabled:opacity-40"
              :disabled="publishing"
              @click="togglePublish"
            >
              {{ publishing ? '…' : 'Снять' }}
            </button>
          </template>
          <button
            class="rounded-xl border border-gray-200 px-4 py-3.5 text-sm font-medium text-gray-500 min-h-[48px]"
            @click="$router.push('/')"
          >
            На главную
          </button>
        </template>
      </div>
    </div>

    <POIModal v-if="selectedPOI" :poi="selectedPOI" :is-open="selectedIsOpen" @close="selectedPOI = null" />
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
const publishing = ref(false)
const showOpeningHours = ref(true)
const selectedPOI = ref<POI | null>(null)
const selectedIsOpen = ref<boolean | null>(null)
const addPointMode = ref(false)
const suggesting = ref(false)
const suggestedPOI = ref<POI | null>(null)
const addError = ref<string | null>(null)

const route = computed(() => store.currentRoute)

const hasOpeningHours = computed(() =>
  route.value?.waypoints.some((wp) => wp.is_open !== null) ?? false,
)

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

async function togglePublish() {
  if (!route.value) return
  publishing.value = true
  try {
    if (route.value.is_published) {
      await store.unpublishRoute(route.value.id)
    } else {
      await store.publishRoute(route.value.id)
    }
  } finally {
    publishing.value = false
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
  const result = await store.updateRoute(route.value.id, { remove_poi_xids: [xid] })
  if (result === null) router.push('/')
}

async function onMapTap(lat: number, lon: number) {
  if (!addPointMode.value || !route.value) return
  suggesting.value = true
  addError.value = null
  suggestedPOI.value = null
  try {
    suggestedPOI.value = await store.suggestWaypoint(route.value.id, lat, lon)
  } catch {
    addError.value = 'Рядом не найдено подходящих мест. Попробуйте другое место.'
  } finally {
    suggesting.value = false
  }
}

async function confirmAdd() {
  if (!suggestedPOI.value || !route.value) return
  try {
    await store.updateRoute(route.value.id, { add_poi_xid: suggestedPOI.value.xid })
    addPointMode.value = false
    suggestedPOI.value = null
  } catch {
    addError.value = 'Не удалось добавить точку. Попробуйте ещё раз.'
    suggestedPOI.value = null
  }
}

function cancelAdd() {
  addPointMode.value = false
  suggestedPOI.value = null
  addError.value = null
}
</script>
