<template>
  <div
    class="flex items-start gap-3 rounded-2xl border border-gray-100 bg-white p-3 shadow-sm cursor-pointer active:bg-gray-50"
    @click="$emit('tap')"
  >
    <!-- Index / visited indicator -->
    <div
      class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-sm font-bold"
      :class="waypoint.is_visited ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'"
    >
      <svg v-if="waypoint.is_visited" class="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
      </svg>
      <span v-else>{{ index + 1 }}</span>
    </div>

    <div class="flex-1 min-w-0">
      <p class="font-medium text-gray-900 truncate">{{ waypoint.poi.name }}</p>
      <p class="text-xs text-gray-400 truncate">
        {{ kindLabel }}
      </p>
    </div>

    <!-- Walk time from previous -->
    <div v-if="waypoint.leg_duration_s" class="flex-shrink-0 text-right">
      <span class="text-xs text-gray-400">~{{ Math.ceil(waypoint.leg_duration_s / 60) }} min</span>
    </div>

    <!-- Edit mode controls -->
    <div v-if="editMode" class="flex flex-shrink-0 flex-col gap-1" @click.stop>
      <button class="flex h-6 w-6 items-center justify-center rounded text-gray-400 hover:text-gray-600 disabled:opacity-30"
        :disabled="index === 0" @click="$emit('move-up')">▲</button>
      <button class="flex h-6 w-6 items-center justify-center rounded text-gray-400 hover:text-gray-600 disabled:opacity-30"
        :disabled="isLast" @click="$emit('move-down')">▼</button>
      <button class="flex h-6 w-6 items-center justify-center rounded text-red-400 hover:text-red-600"
        @click="$emit('remove')">✕</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Waypoint } from '@/types'

const props = defineProps<{
  waypoint: Waypoint
  index: number
  isLast: boolean
  editMode: boolean
}>()

defineEmits<{ tap: []; 'move-up': []; 'move-down': []; remove: [] }>()

const kindLabel = computed(() =>
  props.waypoint.poi.kinds
    .split(',')
    .slice(0, 2)
    .map((k) => k.trim().replace(/_/g, ' '))
    .filter(Boolean)
    .join(' · '),
)
</script>
