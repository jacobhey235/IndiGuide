<template>
  <div class="rounded-2xl bg-white p-4 shadow-sm">
    <h2 class="mb-3 text-sm font-semibold text-gray-700">Мои интересы</h2>

    <div v-if="hasActivity" class="flex items-center justify-center">
      <svg :viewBox="`0 0 ${SIZE} ${SIZE}`" :width="SIZE" :height="SIZE" class="overflow-visible">
        <!-- Reference rings -->
        <polygon
          v-for="level in LEVELS"
          :key="level"
          :points="ringPoints(level)"
          fill="none"
          stroke="#e5e7eb"
          stroke-width="1"
        />
        <!-- Axis lines -->
        <line
          v-for="(cat, i) in categories"
          :key="cat.key"
          :x1="CX"
          :y1="CY"
          :x2="axisPoint(i, 1).x"
          :y2="axisPoint(i, 1).y"
          stroke="#e5e7eb"
          stroke-width="1"
        />
        <!-- Score polygon -->
        <polygon
          :points="scorePoints"
          fill="rgba(59, 130, 246, 0.15)"
          stroke="#3b82f6"
          stroke-width="2"
          stroke-linejoin="round"
        />
        <!-- Score dots -->
        <circle
          v-for="(cat, i) in categories"
          :key="cat.key + '_dot'"
          :cx="axisPoint(i, scoreFor(cat.key)).x"
          :cy="axisPoint(i, scoreFor(cat.key)).y"
          r="4"
          fill="#3b82f6"
        />
        <!-- Emoji labels -->
        <text
          v-for="(cat, i) in categories"
          :key="cat.key + '_label'"
          :x="labelPoint(i).x"
          :y="labelPoint(i).y"
          text-anchor="middle"
          dominant-baseline="middle"
          font-size="18"
        >{{ cat.emoji }}</text>
      </svg>
    </div>

    <div v-else class="py-4 text-center text-xs text-gray-400">
      Интересы формируются по мере прохождения маршрутов
    </div>

    <!-- Legend -->
    <div v-if="hasActivity" class="mt-3 grid grid-cols-2 gap-x-4 gap-y-1">
      <div v-for="cat in categories" :key="cat.key" class="flex items-center gap-1.5">
        <span class="text-sm">{{ cat.emoji }}</span>
        <span class="truncate text-xs text-gray-500">{{ cat.label }}</span>
        <span class="ml-auto text-xs font-medium text-blue-600">{{ pct(scoreFor(cat.key)) }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CATEGORIES } from '@/constants/categories'

const props = defineProps<{
  scores: Record<string, number>
}>()

const SIZE = 220
const CX = SIZE / 2
const CY = SIZE / 2
const RADIUS = 80
const LABEL_OFFSET = 22
const LEVELS = [0.25, 0.5, 0.75, 1.0]
const N = CATEGORIES.length

const categories = CATEGORIES

// angle for axis i: start from top (-π/2), go clockwise
function angle(i: number): number {
  return (i * 2 * Math.PI) / N - Math.PI / 2
}

function axisPoint(i: number, t: number): { x: number; y: number } {
  const a = angle(i)
  return { x: CX + t * RADIUS * Math.cos(a), y: CY + t * RADIUS * Math.sin(a) }
}

function labelPoint(i: number): { x: number; y: number } {
  const a = angle(i)
  return {
    x: CX + (RADIUS + LABEL_OFFSET) * Math.cos(a),
    y: CY + (RADIUS + LABEL_OFFSET) * Math.sin(a),
  }
}

function ringPoints(level: number): string {
  return CATEGORIES.map((_, i) => {
    const p = axisPoint(i, level)
    return `${p.x},${p.y}`
  }).join(' ')
}

function scoreFor(key: string): number {
  return props.scores[key] ?? 0.5
}

const scorePoints = computed(() =>
  CATEGORIES.map((cat, i) => {
    const p = axisPoint(i, scoreFor(cat.key))
    return `${p.x},${p.y}`
  }).join(' '),
)

// "has activity" = at least one score meaningfully differs from 0.5
const hasActivity = computed(() =>
  CATEGORIES.some((cat) => Math.abs(scoreFor(cat.key) - 0.5) > 0.02),
)

function pct(score: number): number {
  return Math.round(score * 100)
}
</script>
