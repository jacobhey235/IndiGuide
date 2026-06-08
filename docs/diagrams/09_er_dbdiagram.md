# Рисунок 5 — ER-диаграмма предметной области

Вставьте код ниже в онлайн-редактор **dbdiagram.io** (https://dbdiagram.io).
Полученное изображение поместите на место «Рисунка 5» в тексте ВКР.

```dbml
Table users {
  id uuid [pk]
  email varchar [unique, not null]
  username varchar(50) [not null]
  hashed_password varchar [not null]
  created_at timestamptz [not null]
}

Table pois {
  xid varchar [pk, note: 'идентификатор объекта в OpenTripMap']
  name varchar [not null]
  lon float [not null]
  lat float [not null]
  kinds varchar [not null, note: 'категории через запятую']
  rate float [not null, note: 'рейтинг OpenTripMap']
  wikipedia_excerpt text
  image_url varchar
  address text
  opening_hours text [note: 'часы работы (OSM)']
  last_fetched_at timestamptz [not null]
  // location geography(Point,4326) — генерируемый столбец PostGIS
}

Table routes {
  id uuid [pk]
  user_id uuid [ref: > users.id, not null]
  name varchar [not null]
  status varchar [not null, note: 'draft / active / completed / abandoned']
  is_saved boolean [not null, default: false]
  is_published boolean [not null, default: false]
  start_lon float [not null]
  start_lat float [not null]
  total_distance_m float [not null]
  osrm_geometry jsonb [note: 'геометрия маршрута GeoJSON']
  leg_geometries jsonb [note: 'геометрия сегментов']
  created_at timestamptz [not null]
  started_at timestamptz
  ended_at timestamptz
  original_author_username varchar [note: 'автор оригинала при копировании']
}

Table route_waypoints {
  id integer [pk, increment]
  route_id uuid [ref: > routes.id, not null]
  poi_xid varchar [ref: > pois.xid, not null]
  order_index integer [not null]
  is_visited boolean [not null, default: false]
  visited_at timestamptz
  leg_duration_s integer [note: 'длительность сегмента, сек']
}

Table user_preferences {
  user_id uuid [ref: > users.id]
  poi_kind varchar [note: 'категория OpenTripMap']
  score float [not null, default: 0.5, note: 'оценка предпочтения 0..1 (EMA)']
  interactions integer [not null, default: 0]
  last_updated_at timestamptz [not null]

  indexes {
    (user_id, poi_kind) [pk]
  }
}

Table poi_interactions {
  id integer [pk, increment]
  user_id uuid [ref: > users.id, not null]
  poi_xid varchar [ref: > pois.xid, not null]
  route_id uuid [ref: > routes.id, note: 'ON DELETE SET NULL']
  interaction_type varchar [not null, note: 'visited / removed / liked / disliked']
  rating integer
  created_at timestamptz [not null]
}
```
