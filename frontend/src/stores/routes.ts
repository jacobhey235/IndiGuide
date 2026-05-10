import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '@/api/client'
import type { GenerateRouteRequest, POI, Route, RouteUpdateRequest } from '@/types'

export const useRoutesStore = defineStore('routes', () => {
  const routes = ref<Route[]>([])
  const currentRoute = ref<Route | null>(null)
  const generating = ref(false)

  async function generateRoute(req: GenerateRouteRequest): Promise<Route> {
    generating.value = true
    try {
      const { data } = await client.post<Route>('/routes/generate', req)
      routes.value.unshift(data)
      currentRoute.value = data
      return data
    } finally {
      generating.value = false
    }
  }

  async function fetchRoutes() {
    const { data } = await client.get<Route[]>('/routes/')
    routes.value = data
  }

  async function fetchRoute(id: string): Promise<Route> {
    const { data } = await client.get<Route>(`/routes/${id}`)
    currentRoute.value = data
    return data
  }

  async function updateRoute(id: string, updates: RouteUpdateRequest): Promise<Route> {
    const { data } = await client.put<Route>(`/routes/${id}`, updates)
    currentRoute.value = data
    const idx = routes.value.findIndex((r) => r.id === id)
    if (idx !== -1) routes.value[idx] = data
    return data
  }

  async function deleteRoute(id: string) {
    await client.delete(`/routes/${id}`)
    routes.value = routes.value.filter((r) => r.id !== id)
    if (currentRoute.value?.id === id) currentRoute.value = null
  }

  async function startRoute(id: string): Promise<Route> {
    const { data } = await client.post<Route>(`/routes/${id}/start`)
    currentRoute.value = data
    return data
  }

  async function endRoute(id: string): Promise<Route> {
    const { data } = await client.post<Route>(`/routes/${id}/end`)
    currentRoute.value = data
    const idx = routes.value.findIndex((r) => r.id === id)
    if (idx !== -1) routes.value[idx] = data
    return data
  }

  async function visitWaypoint(routeId: string, waypointId: number): Promise<Route> {
    const { data } = await client.post<Route>(`/routes/${routeId}/waypoints/${waypointId}/visit`)
    currentRoute.value = data
    return data
  }

  async function saveRoute(id: string): Promise<Route> {
    return updateRoute(id, { is_saved: true })
  }

  async function fetchPOIDetail(xid: string): Promise<POI> {
    const { data } = await client.get<POI>(`/pois/${xid}`)
    return data
  }

  return {
    routes,
    currentRoute,
    generating,
    generateRoute,
    fetchRoutes,
    fetchRoute,
    updateRoute,
    saveRoute,
    deleteRoute,
    startRoute,
    endRoute,
    visitWaypoint,
    fetchPOIDetail,
  }
})
