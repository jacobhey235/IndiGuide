<template>
  <div>
    <button
      ref="buttonRef"
      class="flex items-center gap-1.5 rounded-full bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors min-h-[36px]"
      @click="toggleOpen"
    >
      <svg class="h-3.5 w-3.5 flex-shrink-0 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"/>
      </svg>
      <span class="max-w-[100px] truncate">{{ currentCity }}</span>
    </button>

    <Teleport to="body">
      <div v-if="open" class="fixed inset-0 z-30" @click="open = false" />
      <div
        v-if="open"
        class="fixed z-40 w-64 rounded-xl bg-white shadow-xl border border-gray-100 overflow-hidden"
        :style="dropdownStyle"
      >
        <div class="p-2">
          <input
            ref="inputRef"
            v-model="query"
            type="text"
            placeholder="Поиск города…"
            class="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
            @input="onInput"
          />
        </div>

        <div class="max-h-60 overflow-y-auto">
          <template v-if="searching">
            <div class="px-4 py-3 text-sm text-gray-400">Поиск…</div>
          </template>
          <template v-else-if="searchResults.length">
            <button
              v-for="r in searchResults"
              :key="r.name + r.lat"
              class="w-full px-4 py-2.5 text-left text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              @click="select(r)"
            >{{ r.name }}</button>
          </template>
          <template v-else-if="query.length >= 2">
            <div class="px-4 py-3 text-sm text-gray-400">Ничего не найдено</div>
          </template>
          <template v-else>
            <div class="px-3 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">Крупные города</div>
            <button
              v-for="c in CITIES"
              :key="c.name"
              class="w-full px-4 py-2.5 text-left text-sm transition-colors"
              :class="c.name === currentCity ? 'text-blue-600 font-medium bg-blue-50' : 'text-gray-700 hover:bg-gray-50'"
              @click="select(c)"
            >{{ c.name }}</button>
          </template>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'

interface City { name: string; lat: number; lon: number }

const CITIES: City[] = [
  { name: 'Москва', lat: 55.7558, lon: 37.6173 },
  { name: 'Санкт-Петербург', lat: 59.9311, lon: 30.3609 },
  { name: 'Новосибирск', lat: 54.9885, lon: 82.9207 },
  { name: 'Екатеринбург', lat: 56.8391, lon: 60.6057 },
  { name: 'Казань', lat: 55.8304, lon: 49.0661 },
  { name: 'Нижний Новгород', lat: 56.2965, lon: 43.9361 },
  { name: 'Челябинск', lat: 55.1644, lon: 61.4368 },
  { name: 'Омск', lat: 54.9924, lon: 73.3686 },
  { name: 'Самара', lat: 53.1959, lon: 50.1002 },
  { name: 'Уфа', lat: 54.7388, lon: 55.9721 },
  { name: 'Ростов-на-Дону', lat: 47.2357, lon: 39.7015 },
  { name: 'Красноярск', lat: 56.0153, lon: 92.8932 },
]

const emit = defineEmits<{ select: [lat: number, lon: number, name: string] }>()

const open = ref(false)
const query = ref('')
const currentCity = ref('Москва')
const searching = ref(false)
const searchResults = ref<City[]>([])
const buttonRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLInputElement | null>(null)

let debounceTimer: ReturnType<typeof setTimeout> | null = null

const dropdownStyle = computed(() => {
  if (!buttonRef.value) return {}
  const rect = buttonRef.value.getBoundingClientRect()
  return { top: `${rect.bottom + 4}px`, left: `${rect.left}px` }
})

watch(open, (val) => {
  if (val) {
    query.value = ''
    searchResults.value = []
    nextTick(() => inputRef.value?.focus())
  }
})

function toggleOpen() {
  open.value = !open.value
}

function onInput() {
  if (debounceTimer) clearTimeout(debounceTimer)
  if (query.value.length < 2) { searchResults.value = []; return }
  debounceTimer = setTimeout(geocode, 400)
}

async function geocode() {
  searching.value = true
  try {
    await ymaps.ready()
    const res = await ymaps.geocode(query.value, { results: 5, kind: 'locality' })
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    searchResults.value = res.geoObjects.toArray().map((obj: any) => {
      const coords = obj.geometry.getCoordinates() as [number, number]
      return { name: obj.getAddressLine() as string, lat: coords[0], lon: coords[1] }
    })
  } catch {
    searchResults.value = []
  } finally {
    searching.value = false
  }
}

function select(city: City) {
  currentCity.value = city.name
  open.value = false
  query.value = ''
  searchResults.value = []
  localStorage.setItem('lastCity', JSON.stringify(city))
  emit('select', city.lat, city.lon, city.name)
}

onMounted(() => {
  const saved = localStorage.getItem('lastCity')
  if (saved) {
    try {
      const city: City = JSON.parse(saved)
      currentCity.value = city.name
      emit('select', city.lat, city.lon, city.name)
    } catch {
      localStorage.removeItem('lastCity')
    }
  }
})
</script>
