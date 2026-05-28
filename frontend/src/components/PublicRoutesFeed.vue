<template>
  <div class="flex flex-col h-full">
    <!-- Sort toggle -->
    <div class="px-4 pt-3 pb-2 flex-shrink-0">
      <div class="flex bg-gray-100 rounded-xl p-1">
        <button
          class="flex-1 py-2 text-xs font-medium rounded-lg transition-all"
          :class="sort === 'preferences' ? 'bg-white shadow text-gray-900' : 'text-gray-500'"
          @click="setSort('preferences')"
        >
          По интересам
        </button>
        <button
          class="flex-1 py-2 text-xs font-medium rounded-lg transition-all"
          :class="sort === 'categories' ? 'bg-white shadow text-gray-900' : 'text-gray-500'"
          @click="setSort('categories')"
        >
          По категориям
        </button>
      </div>

      <!-- Category chips (visible when sort=categories) -->
      <div v-if="sort === 'categories'" class="flex flex-wrap gap-1.5 mt-2">
        <button
          v-for="cat in CATEGORIES"
          :key="cat.key"
          class="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border transition-all"
          :class="selectedCategories.includes(cat.key)
            ? 'bg-blue-600 border-blue-600 text-white'
            : 'bg-white border-gray-200 text-gray-600'"
          @click="toggleCategory(cat.key)"
        >
          <span>{{ cat.emoji }}</span>
          <span>{{ cat.label }}</span>
        </button>
      </div>
    </div>

    <!-- Route list -->
    <div class="flex-1 overflow-y-auto">
      <div v-if="loading" class="flex items-center justify-center py-12 text-gray-400">
        <svg class="h-6 w-6 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
        </svg>
      </div>

      <div v-else-if="routes.length === 0" class="flex flex-col items-center justify-center py-16 px-4 text-center">
        <p class="text-gray-400 text-sm">
          {{ sort === 'categories' && selectedCategories.length > 0
            ? 'Маршрутов по выбранным категориям не найдено'
            : 'Опубликованных маршрутов пока нет' }}
        </p>
      </div>

      <div v-else class="divide-y divide-gray-50">
        <button
          v-for="route in routes"
          :key="route.id"
          class="w-full px-4 py-3 text-left hover:bg-gray-50 active:bg-gray-100 transition-colors"
          @click="$emit('select', route.id)"
        >
          <div class="flex items-start gap-2">
            <div class="flex-1 min-w-0">
              <p class="font-semibold text-gray-900 truncate text-sm">{{ route.name }}</p>
              <p class="text-xs text-blue-600 mt-0.5">@{{ route.author_username }}</p>
              <p class="text-xs text-gray-400 mt-0.5">
                {{ (route.total_distance_m / 1000).toFixed(1) }} км · {{ route.waypoints.length }} остановок
              </p>
              <div class="mt-1.5 flex flex-wrap gap-1">
                <span
                  v-for="kind in topKinds(route)"
                  :key="kind"
                  class="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-600"
                >{{ kind }}</span>
              </div>
            </div>
            <svg class="w-4 h-4 text-gray-300 flex-shrink-0 mt-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoutesStore } from '@/stores/routes'
import { CATEGORIES } from '@/constants/categories'
import type { PublicRoute } from '@/types'
import { translateKind } from '@/constants/kindTranslations'

const emit = defineEmits<{ select: [id: string] }>()

const store = useRoutesStore()
const loading = ref(false)
const routes = ref<PublicRoute[]>([])
const sort = ref<'preferences' | 'categories'>('preferences')
const selectedCategories = ref<string[]>([])

async function load() {
  loading.value = true
  try {
    routes.value = await store.fetchExploreRoutes(sort.value, selectedCategories.value)
  } finally {
    loading.value = false
  }
}

function setSort(s: 'preferences' | 'categories') {
  sort.value = s
  if (s === 'categories' && selectedCategories.value.length === 0) {
    selectedCategories.value = CATEGORIES.map((c) => c.key)
  }
  load()
}

function toggleCategory(key: string) {
  const idx = selectedCategories.value.indexOf(key)
  if (idx === -1) {
    selectedCategories.value.push(key)
  } else {
    selectedCategories.value.splice(idx, 1)
  }
  load()
}

function topKinds(route: PublicRoute): string[] {
  const counts: Record<string, number> = {}
  for (const wp of route.waypoints) {
    for (const k of (wp.poi.kinds ?? '').split(',').map((s) => s.trim()).filter(Boolean)) {
      counts[k] = (counts[k] ?? 0) + 1
    }
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([k]) => translateKind(k))
}

onMounted(load)
</script>
