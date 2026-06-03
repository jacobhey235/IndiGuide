const DAY_TRANSLATIONS: Record<string, string> = {
  Mo: 'Пн',
  Tu: 'Вт',
  We: 'Ср',
  Th: 'Чт',
  Fr: 'Пт',
  Sa: 'Сб',
  Su: 'Вс',
}

// Occurrence qualifiers: [1]=1-й, [2]=2-й, ..., [-1]=посл., [-2]=предпосл.
const OCCURRENCE_TRANSLATIONS: Record<string, string> = {
  '[-1]': '(посл.)',
  '[-2]': '(предпосл.)',
  '[1]': '(1-й)',
  '[2]': '(2-й)',
  '[3]': '(3-й)',
  '[4]': '(4-й)',
  '[5]': '(5-й)',
}

export function translateOpeningHours(str: string): string {
  return str
    .replace(/\b(Mo|Tu|We|Th|Fr|Sa|Su)\b/g, (m) => DAY_TRANSLATIONS[m] ?? m)
    .replace(/\[(-?\d+)\]/g, (m) => OCCURRENCE_TRANSLATIONS[m] ?? m)
    .replace(/\boff\b/gi, 'вых.')
    .replace(/\bPH\b/g, 'праздн.')
    .replace(/\bSH\b/g, 'кан.')
}
