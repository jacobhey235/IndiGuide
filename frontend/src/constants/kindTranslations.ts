const KIND_TRANSLATIONS: Record<string, string> = {
  // Top-level categories
  historic: 'Памятники',
  architecture: 'Архитектура',
  museums: 'Музеи',
  religion: 'Религия',
  cultural: 'Культура',
  natural: 'Природа',
  interesting_places: 'Достопримечательности',

  // Historic sub-kinds
  historical_places: 'Памятники истории',
  monuments_and_memorials: 'Памятники и мемориалы',
  historic_architecture: 'Памятники архитектуры',
  fortifications: 'Укрепления',
  castles: 'Замки',
  ruins: 'Руины',
  archaeological_sites: 'Раскопки',
  burial_places: 'Захоронения',
  battlefields: 'Поля сражений',
  historic_object: 'Памятник',
  historical_object: 'Памятник',

  // Architecture sub-kinds
  towers: 'Башни',
  bridges: 'Мосты',
  lighthouses: 'Маяки',
  skyscrapers: 'Небоскрёбы',
  urban_environment: 'Городская среда',
  palaces: 'Дворцы',

  // Museums sub-kinds
  art_galleries: 'Галереи',
  science_museums: 'Музеи науки',
  history_museums: 'Музеи истории',
  military_museums: 'Военные музеи',
  children_museums: 'Детские музеи',
  archaeological_museums: 'Музеи археологии',
  ethnographical_museums: 'Этнографические музеи',
  open_air_museums: 'Музеи под открытым небом',

  // Religion sub-kinds
  churches: 'Церкви',
  cathedrals: 'Соборы',
  monasteries: 'Монастыри',
  chapels: 'Часовни',
  mosques: 'Мечети',
  synagogues: 'Синагоги',
  buddhist_temples: 'Буддийские храмы',
  hindu_temples: 'Индуистские храмы',
  shrines: 'Святыни',
  cemeteries: 'Кладбища',

  // Cultural sub-kinds
  theatres_and_entertainments: 'Театры и развлечения',
  theatres: 'Театры',
  cinemas: 'Кинотеатры',
  concert_halls: 'Концертные залы',
  opera_houses: 'Опера',
  zoos: 'Зоопарки',
  aquariums: 'Аквариумы',
  circuses: 'Цирки',
  cultural_centres: 'Культурные центры',
  libraries: 'Библиотеки',

  // Natural sub-kinds
  gardens_and_parks: 'Сады и парки',
  national_parks: 'Парки',
  nature_reserves: 'Заповедники',
  beaches: 'Пляжи',
  waterfalls: 'Водопады',
  viewpoints: 'Смотровые площадки',
  geological_formations: 'Геология',
  caves: 'Пещеры',
  islands: 'Острова',
  mountains: 'Горы',
  springs: 'Родники',
  rivers: 'Реки',
  lakes: 'Озёра',
  forests: 'Леса',

  // Interesting places sub-kinds
  amusements: 'Развлечения',
  tourist_facilities: 'Достопримечательности',
  sport: 'Спорт',
  other: 'Прочее',
  unclassified: 'Прочее',
}

export function translateKind(kind: string): string {
  return KIND_TRANSLATIONS[kind.trim()] ?? kind.trim().replace(/_/g, ' ')
}
