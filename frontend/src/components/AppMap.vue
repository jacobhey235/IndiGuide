<template>
  <div id="yandex-map" class="w-full h-full" />
</template>

<script setup lang="ts">
import { watch } from 'vue'
import { useYandexMap } from '@/composables/useYandexMap'
import type { Route } from '@/types'

const props = defineProps<{
  route?: Route | null
  selectedLat?: number | null
  selectedLon?: number | null
  clickable?: boolean
}>()

const emit = defineEmits<{
  'point-selected': [lat: number, lon: number]
}>()

const { isReady, clearObjects, addPlacemark, drawRoute, drawSegment, onMapClick, panTo, fitViewport } =
  useYandexMap('yandex-map')

watch(isReady, (ready) => {
  if (!ready) return
  if (props.clickable) {
    onMapClick((lat, lon) => emit('point-selected', lat, lon))
  }
  renderRoute()
})

watch(
  [() => props.route, () => props.selectedLat, () => props.selectedLon],
  () => { if (isReady.value) renderRoute() },
)

function renderRoute() {
  clearObjects()

  if (props.selectedLat != null && props.selectedLon != null) {
    addPlacemark(props.selectedLat, props.selectedLon, { hintContent: 'Start point' }, {
      preset: 'islands#greenDotIcon',
    })
  }

  if (!props.route) return

  const isActive = props.route.status === 'active'
  const sorted = [...props.route.waypoints].sort((a, b) => a.order_index - b.order_index)

  if (props.route.osrm_geometry) {
    drawRoute(props.route.osrm_geometry, isActive ? { strokeOpacity: 0.2 } : {})
  }

  if (isActive) {
    const lastVisited = [...sorted].reverse().find(wp => wp.is_visited)
    const nextUnvisited = sorted.find(wp => !wp.is_visited)
    if (nextUnvisited) {
      const from: [number, number] = lastVisited
        ? [lastVisited.poi.lat, lastVisited.poi.lon]
        : [props.route.start_lat, props.route.start_lon]
      drawSegment(from, [nextUnvisited.poi.lat, nextUnvisited.poi.lon])
    }
  }

  sorted.forEach((wp, i) => {
    addPlacemark(
      wp.poi.lat,
      wp.poi.lon,
      {
        balloonContent: wp.poi.name,
        hintContent: wp.poi.name,
        iconContent: wp.is_visited ? '✓' : String(i + 1),
      },
      {
        preset: wp.is_visited ? 'islands#greenStretchyIcon' : 'islands#blueStretchyIcon',
      },
    )
  })
}

defineExpose({ panTo, fitViewport, clearObjects })
</script>
