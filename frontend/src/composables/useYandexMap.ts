import { onMounted, onUnmounted, ref, shallowRef } from 'vue'

const LEG_COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4', '#8b5cf6', '#ec4899']

export function useYandexMap(containerId: string, initialCenter: [number, number] = [55.7558, 37.6173]) {
  // shallowRef prevents Vue from wrapping the Yandex Maps instance in a deep reactive proxy,
  // which breaks internal Yandex Maps event handling and degrades performance over time.
  const mapInstance = shallowRef<ymaps.Map | null>(null)
  const isReady = ref(false)
  let _clickHandler: ((e: ymaps.YMapsEvent) => void) | null = null

  onMounted(async () => {
    await ymaps.ready()
    mapInstance.value = new ymaps.Map(containerId, { center: initialCenter, zoom: 13 }, {
      suppressMapOpenBlock: true,
    })
    isReady.value = true
  })

  onUnmounted(() => {
    if (_clickHandler) {
      mapInstance.value?.events.remove('click', _clickHandler)
      _clickHandler = null
    }
    mapInstance.value?.destroy()
    mapInstance.value = null
    isReady.value = false
  })

  function clearObjects() {
    mapInstance.value?.geoObjects.removeAll()
  }

  function addPlacemark(
    lat: number,
    lon: number,
    props: ymaps.PlacemarkProperties = {},
    opts: ymaps.PlacemarkOptions = {},
  ): ymaps.Placemark {
    const mark = new ymaps.Placemark([lat, lon], props, opts)
    mapInstance.value?.geoObjects.add(mark)
    return mark
  }

  function drawRoute(
    geojson: { type: string; coordinates: [number, number][] },
    overrides: ymaps.PolylineOptions = {},
  ) {
    // GeoJSON [lon, lat] → Yandex Maps [lat, lon]
    const coords = geojson.coordinates.map(([lon, lat]): [number, number] => [lat, lon])
    const polyline = new ymaps.Polyline(coords, {}, {
      strokeColor: '#3b82f6',
      strokeWidth: 4,
      strokeOpacity: 0.85,
      ...overrides,
    })
    mapInstance.value?.geoObjects.add(polyline)
    return polyline
  }

  function drawSegmentedRoute(
    legs: Array<{ type: string; coordinates: [number, number][] }>,
    overrides: ymaps.PolylineOptions = {},
  ) {
    legs.forEach((leg, i) => {
      const coords = leg.coordinates.map(([lon, lat]): [number, number] => [lat, lon])
      const polyline = new ymaps.Polyline(coords, {}, {
        strokeColor: LEG_COLORS[i % LEG_COLORS.length],
        strokeWidth: 4,
        strokeOpacity: 0.85,
        ...overrides,
      })
      mapInstance.value?.geoObjects.add(polyline)
    })
  }

  // Straight-line segment between two [lat, lon] points (used for active-leg highlight)
  function drawSegment(
    from: [number, number],
    to: [number, number],
    overrides: ymaps.PolylineOptions = {},
  ) {
    const polyline = new ymaps.Polyline([from, to], {}, {
      strokeColor: '#2563eb',
      strokeWidth: 6,
      strokeOpacity: 1.0,
      ...overrides,
    })
    mapInstance.value?.geoObjects.add(polyline)
    return polyline
  }

  function onMapClick(handler: (lat: number, lon: number) => void) {
    if (_clickHandler) {
      mapInstance.value?.events.remove('click', _clickHandler)
    }
    _clickHandler = (e) => {
      const coords = e.get('coords') as [number, number]
      handler(coords[0], coords[1])
    }
    mapInstance.value?.events.add('click', _clickHandler)
  }

  function panTo(lat: number, lon: number, zoom = 15) {
    mapInstance.value?.setCenter([lat, lon], zoom)
  }

  function fitToBounds(latLons: [number, number][], bottomPadding = 0) {
    if (!latLons.length || !mapInstance.value) return

    const lats = latLons.map(c => c[0])
    const lons = latLons.map(c => c[1])
    const maxLat = Math.max(...lats)
    const minLat = Math.min(...lats)
    const minLon = Math.min(...lons)
    const maxLon = Math.max(...lons)

    // Pass asymmetric zoomMargin so setBounds keeps the segment inside the visible
    // area above the bottom card. The bottom margin = base + card height pushes the
    // fitting rectangle up exactly to the card's top edge.
    const base = 48
    mapInstance.value.setBounds(
      [[minLat, minLon], [maxLat, maxLon]],
      { checkZoomRange: true, zoomMargin: bottomPadding > 0 ? [base, base, base + bottomPadding, base] : base },
    )
  }

  function fitViewport() {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(mapInstance.value as any)?.container?.fitToViewport()
  }

  return { mapInstance, isReady, clearObjects, addPlacemark, drawRoute, drawSegmentedRoute, drawSegment, onMapClick, panTo, fitToBounds, fitViewport }
}
