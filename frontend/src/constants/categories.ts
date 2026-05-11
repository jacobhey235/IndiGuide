// UI-facing POI categories. Keep keys in sync with
// backend/app/services/route_categories.py.

export interface Category {
  key: string
  label: string
  emoji: string
}

export const CATEGORIES: Category[] = [
  { key: 'historic', label: 'Исторические', emoji: '🏛️' },
  { key: 'architecture', label: 'Архитектура', emoji: '🏰' },
  { key: 'museums', label: 'Музеи', emoji: '🖼️' },
  { key: 'religion', label: 'Религия', emoji: '⛪' },
  { key: 'cultural', label: 'Культура', emoji: '🎭' },
  { key: 'natural', label: 'Парки и природа', emoji: '🌳' },
  { key: 'interesting_places', label: 'Другие места', emoji: '✨' },
]
