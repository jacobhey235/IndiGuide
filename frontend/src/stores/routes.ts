import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '@/api/client'
import type { GenerateRouteRequest, POI, PublicRoute, Route, RouteUpdateRequest } from '@/types'

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

  async function rateWaypoint(routeId: string, waypointId: number, rating: number): Promise<void> {
    await client.post(`/routes/${routeId}/waypoints/${waypointId}/rate`, { rating })
  }

  async function saveRoute(id: string): Promise<Route> {
    return updateRoute(id, { is_saved: true })
  }

  async function publishRoute(id: string): Promise<Route> {
    return updateRoute(id, { is_published: true })
  }

  async function unpublishRoute(id: string): Promise<Route> {
    return updateRoute(id, { is_published: false })
  }

  async function fetchPOIDetail(xid: string): Promise<POI> {
    const { data } = await client.get<POI>(`/pois/${xid}`)
    return data
  }

  async function fetchExploreRoutes(sort: 'preferences' | 'categories', categories?: string[]): Promise<PublicRoute[]> {
    const params: Record<string, string> = { sort }
    if (sort === 'categories' && categories?.length) {
      params.categories = categories.join(',')
    }
    const { data } = await client.get<PublicRoute[]>('/routes/explore', { params })
    return data
  }

  async function fetchExploreRoute(id: string): Promise<PublicRoute> {
    const { data } = await client.get<PublicRoute>(`/routes/explore/${id}`)
    return data
  }

  async function cloneExploreRoute(id: string): Promise<Route> {
    const { data } = await client.post<Route>(`/routes/explore/${id}/clone`)
    currentRoute.value = data
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
    publishRoute,
    unpublishRoute,
    deleteRoute,
    startRoute,
    endRoute,
    visitWaypoint,
    rateWaypoint,
    fetchPOIDetail,
    fetchExploreRoutes,
    fetchExploreRoute,
    cloneExploreRoute,
  }
})
