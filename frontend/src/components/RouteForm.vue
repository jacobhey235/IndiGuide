<template>
  <div class="px-4 pb-4 pt-2">
    <h2 class="mb-4 text-lg font-bold text-gray-900">Создать маршрут</h2>

    <div v-if="selectedLat" class="mb-4 flex items-center gap-2 rounded-xl bg-green-50 px-3 py-2">
      <svg class="h-4 w-4 flex-shrink-0 text-green-600" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"/>
      </svg>
      <span class="text-sm text-green-700">Начальная точка выбрана · нажмите на карту, чтобы изменить</span>
    </div>
    <p v-else class="mb-4 rounded-xl bg-blue-50 px-3 py-2 text-sm text-blue-600">
      Нажмите на карту, чтобы выбрать начальную точку
    </p>

    <div class="space-y-4">
      <div>
        <div class="mb-1 flex justify-between text-sm">
          <label class="font-medium text-gray-700">Расстояние</label>
          <span class="text-gray-500">{{ (form.distance_m / 1000).toFixed(1) }} км</span>
        </div>
        <input
          v-model.number="form.distance_m"
          type="range" min="500" max="15000" step="500"
          class="w-full accent-blue-600"
        />
        <div class="mt-1 flex justify-between text-xs text-gray-400">
          <span>0.5 км</span><span>15 км</span>
        </div>
      </div>

      <div>
        <div class="mb-1 flex justify-between text-sm">
          <label class="font-medium text-gray-700">Число объектов</label>
          <span class="text-gray-500">{{ form.num_pois }}</span>
        </div>
        <input
          v-model.number="form.num_pois"
          type="range" min="2" :max="maxPois" step="1"
          class="w-full accent-blue-600"
        />
        <div class="mt-1 flex justify-between text-xs text-gray-400">
          <span>2</span><span>{{ maxPois }}</span>
        </div>
      </div>

      <div>
        <label class="mb-2 block text-sm font-medium text-gray-700">
          Что вас интересует
        </label>

        <div class="mb-3 flex overflow-hidden rounded-lg border border-gray-200 text-xs font-medium">
          <button
            type="button"
            class="flex-1 py-2 transition-colors"
            :class="usePrefs ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'"
            @click="usePrefs = true"
          >По предпочтениям</button>
          <button
            type="button"
            class="flex-1 border-l border-gray-200 py-2 transition-colors"
            :class="!usePrefs ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50'"
            @click="usePrefs = false"
          >Выбрать вручную</button>
        </div>

        <p v-if="usePrefs" class="text-xs text-gray-500">
          Маршрут подберётся по вашим интересам автоматически
        </p>

        <div v-else class="flex flex-wrap gap-2">
          <button
            v-for="c in CATEGORIES"
            :key="c.key"
            type="button"
            class="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors min-h-[36px]"
            :class="selected.has(c.key)
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'"
            @click="toggle(c.key)"
          >
            <span>{{ c.emoji }}</span>
            <span>{{ c.label }}</span>
          </button>
        </div>
        <p v-if="!usePrefs && selected.size === 0" class="mt-2 text-xs text-gray-400">
          Выберите хотя бы одну категорию
        </p>
      </div>

      <label class="flex items-center gap-3 cursor-pointer select-none py-1">
        <span class="relative inline-flex h-6 w-11 flex-shrink-0">
          <input type="checkbox" class="peer sr-only" v-model="filterOpenNow" />
          <span class="h-6 w-11 rounded-full bg-gray-200 transition peer-checked:bg-blue-500"></span>
          <span class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition peer-checked:translate-x-5"></span>
        </span>
        <span class="text-sm text-gray-600">Только открытые сейчас</span>
      </label>

      <label class="flex items-center gap-3 cursor-pointer select-none py-1">
        <span class="relative inline-flex h-6 w-11 flex-shrink-0">
          <input type="checkbox" class="peer sr-only" v-model="includeDisliked" />
          <span class="h-6 w-11 rounded-full bg-gray-200 transition peer-checked:bg-blue-500"></span>
          <span class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition peer-checked:translate-x-5"></span>
        </span>
        <span class="text-sm text-gray-600">Показывать нелюбимые места</span>
      </label>

      <button
        :disabled="!selectedLat || loading || (!usePrefs && selected.size === 0)"
        class="w-full rounded-xl bg-blue-600 py-3.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40 min-h-[48px]"
        @click="submit"
      >
        <span v-if="loading" class="flex items-center justify-center gap-2">
          <svg class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
          </svg>
          Создание маршрута…
        </span>
        <span v-else>Создать маршрут</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, watch } from 'vue'
import { CATEGORIES } from '@/constants/categories'

const props = defineProps<{
  selectedLat?: number | null
  selectedLon?: number | null
  loading: boolean
}>()

const emit = defineEmits<{
  generate: [req: { distance_m: number; num_pois: number; selected_categories?: string[]; include_disliked?: boolean; filter_open_now?: boolean; client_utc_offset?: number }]
}>()

const form = reactive({ distance_m: 3000, num_pois: 4 })

const maxPois = computed(() => Math.max(2, Math.min(10, Math.floor(form.distance_m / 750))))

watch(maxPois, (max) => {
  if (form.num_pois > max) form.num_pois = max
})
const usePrefs = ref(true)
const selected = ref<Set<string>>(new Set(['historic', 'architecture']))
const includeDisliked = ref(false)
const filterOpenNow = ref(false)

function toggle(key: string) {
  const next = new Set(selected.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  selected.value = next
}

function submit() {
  if (!props.selectedLat) return
  if (!usePrefs.value && selected.value.size === 0) return
  emit('generate', {
    distance_m: form.distance_m,
    num_pois: form.num_pois,
    ...(usePrefs.value ? {} : { selected_categories: Array.from(selected.value) }),
    ...(includeDisliked.value ? { include_disliked: true } : {}),
    ...(filterOpenNow.value ? { filter_open_now: true, client_utc_offset: -new Date().getTimezoneOffset() } : {}),
  })
}
</script>
