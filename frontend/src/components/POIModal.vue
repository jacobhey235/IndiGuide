<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-end bg-black/50"
      @click.self="$emit('close')"
    >
      <div class="max-h-[80dvh] w-full overflow-y-auto rounded-t-3xl bg-white safe-bottom">
        <!-- Image -->
        <div v-if="poi.image_url" class="relative h-48 w-full overflow-hidden">
          <img :src="poi.image_url" :alt="poi.name" class="h-full w-full object-cover" />
          <button
            class="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-full bg-black/40 text-white"
            @click="$emit('close')"
          >
            ✕
          </button>
        </div>

        <div class="p-5">
          <div class="mb-1 flex items-start justify-between gap-2">
            <h2 class="text-xl font-bold text-gray-900">{{ poi.name }}</h2>
            <button v-if="!poi.image_url" class="text-gray-400" @click="$emit('close')">✕</button>
          </div>

          <!-- Kinds pills -->
          <div class="mb-3 flex flex-wrap gap-1">
            <span
              v-for="kind in kindsList"
              :key="kind"
              class="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700"
            >
              {{ kind }}
            </span>
          </div>

          <!-- Opening hours -->
          <div v-if="openingHours" class="mb-3 flex items-start gap-1.5 text-sm text-gray-500">
            <svg class="h-4 w-4 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <div>
              <span>{{ openingHours }}</span>
              <span
                v-if="isOpen === true"
                class="ml-2 rounded-full bg-green-100 px-1.5 py-0.5 text-[10px] font-medium text-green-700"
              >Открыто</span>
              <span
                v-else-if="isOpen === false"
                class="ml-2 rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-700"
              >Закрыто</span>
            </div>
          </div>

          <!-- Address -->
          <p v-if="poi.address" class="mb-3 flex items-center gap-1.5 text-sm text-gray-500">
            <svg class="h-4 w-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
            </svg>
            {{ poi.address }}
          </p>

          <!-- Wikipedia excerpt -->
          <div v-if="loading" class="flex items-center gap-2 text-sm text-gray-400">
            <svg class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
            </svg>
            Загрузка описания…
          </div>
          <div v-else-if="detail?.wikipedia_excerpt" class="prose prose-sm max-w-none text-gray-700">
            <p class="leading-relaxed">{{ detail.wikipedia_excerpt }}</p>
          </div>
          <p v-else class="text-sm text-gray-400 italic">Описание недоступно.</p>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoutesStore } from '@/stores/routes'
import type { POI } from '@/types'
import { translateKind } from '@/constants/kindTranslations'
import { translateOpeningHours } from '@/constants/openingHoursTranslation'

const props = defineProps<{ poi: POI; isOpen?: boolean | null }>()
defineEmits<{ close: [] }>()

const store = useRoutesStore()
const detail = ref<POI | null>(null)
const loading = ref(false)

const kindsList = computed(() =>
  props.poi.kinds
    .split(',')
    .map(translateKind)
    .filter(Boolean)
    .slice(0, 5),
)

const openingHours = computed(() => {
  const raw = detail.value?.opening_hours || props.poi.opening_hours || null
  return raw ? translateOpeningHours(raw) : null
})
const isOpen = computed(() => props.isOpen ?? null)

onMounted(async () => {
  if (props.poi.wikipedia_excerpt) {
    detail.value = props.poi
    return
  }
  loading.value = true
  try {
    detail.value = await store.fetchPOIDetail(props.poi.xid)
  } finally {
    loading.value = false
  }
})
</script>
