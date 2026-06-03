const DAY_TRANSLATIONS: Record<string, string> = {
  Mo: 'Пн',
  Tu: 'Вт',
  We: 'Ср',
  Th: 'Чт',
  Fr: 'Пт',
  Sa: 'Сб',
  Su: 'Вс',
}

export function translateOpeningHours(str: string): string {
  return str.replace(/\b(Mo|Tu|We|Th|Fr|Sa|Su)\b/g, (m) => DAY_TRANSLATIONS[m] ?? m)
}
