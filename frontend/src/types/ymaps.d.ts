/* Minimal Yandex Maps 2.1 type stubs — only what IndiGuide uses */
declare namespace ymaps {
  function ready(): Promise<void>

  interface MapState {
    center: [number, number]
    zoom: number
    controls?: string[]
  }

  interface MapOptions {
    suppressMapOpenBlock?: boolean
  }

  interface EventManager {
    add(event: string, handler: (e: YMapsEvent) => void): void
    remove(event: string, handler: (e: YMapsEvent) => void): void
  }

  interface YMapsEvent {
    get(key: 'coords'): [number, number]
    get(key: string): unknown
  }

  interface GeoObjectCollection {
    add(obj: Placemark | Polyline | GeoObject): this
    remove(obj: Placemark | Polyline | GeoObject): this
    removeAll(): this
  }

  interface GeoObject {
    events: EventManager
  }

  class Map {
    constructor(element: string | HTMLElement, state: MapState, options?: MapOptions)
    geoObjects: GeoObjectCollection
    events: EventManager
    setCenter(coords: [number, number], zoom?: number, options?: object): Promise<void>
    getBounds(): [[number, number], [number, number]]
    setBounds(bounds: [[number, number], [number, number]], options?: object): Promise<void>
    destroy(): void
  }

  interface PlacemarkProperties {
    balloonContent?: string
    hintContent?: string
    iconContent?: string
  }

  interface PlacemarkOptions {
    preset?: string
    iconColor?: string
    draggable?: boolean
  }

  class Placemark implements GeoObject {
    constructor(
      geometry: [number, number],
      properties?: PlacemarkProperties,
      options?: PlacemarkOptions
    )
    events: EventManager
    geometry: { getCoordinates(): [number, number] }
  }

  interface PolylineOptions {
    strokeColor?: string
    strokeWidth?: number
    strokeOpacity?: number
  }

  class Polyline implements GeoObject {
    constructor(geometry: [number, number][], properties?: object, options?: PolylineOptions)
    events: EventManager
  }

  interface GeoObjectList {
    toArray(): GeoObject[]
  }

  interface GeocodeResult {
    geoObjects: GeoObjectList
  }

  interface GeocodeOptions {
    results?: number
    kind?: string
  }

  function geocode(request: string, options?: GeocodeOptions): Promise<GeocodeResult>
}

declare const ymaps: typeof ymaps & { ready: () => Promise<void> }
