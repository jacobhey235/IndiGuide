export interface User {
  id: string
  email: string
  username: string
  created_at: string
}

export type RouteStatus = 'draft' | 'active' | 'completed' | 'abandoned'

export interface POI {
  xid: string
  name: string
  lon: number
  lat: number
  kinds: string
  rate: number
  wikipedia_excerpt?: string | null
  image_url?: string | null
  address?: string | null
}

export interface Waypoint {
  id: number
  poi_xid: string
  order_index: number
  is_visited: boolean
  visited_at?: string | null
  leg_duration_s?: number | null
  poi: POI
}

export interface Route {
  id: string
  name: string
  status: RouteStatus
  is_saved: boolean
  is_published: boolean
  start_lon: number
  start_lat: number
  total_distance_m: number
  osrm_geometry?: { type: 'LineString'; coordinates: [number, number][] } | null
  leg_geometries?: Array<{ type: 'LineString'; coordinates: [number, number][] }> | null
  created_at: string
  started_at?: string | null
  ended_at?: string | null
  waypoints: Waypoint[]
  author_username?: string
}

export interface PublicRoute {
  id: string
  name: string
  status: RouteStatus
  total_distance_m: number
  start_lon: number
  start_lat: number
  osrm_geometry?: { type: 'LineString'; coordinates: [number, number][] } | null
  leg_geometries?: Array<{ type: 'LineString'; coordinates: [number, number][] }> | null
  created_at: string
  started_at?: string | null
  ended_at?: string | null
  waypoints: Waypoint[]
  author_username: string
}

export interface GenerateRouteRequest {
  start_lat: number
  start_lon: number
  distance_m: number
  num_pois: number
  selected_categories?: string[]
  name?: string
}

export interface RouteUpdateRequest {
  name?: string
  waypoint_order?: string[]
  remove_poi_xids?: string[]
  is_saved?: boolean
  is_published?: boolean
}
