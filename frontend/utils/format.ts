/** Рубли для витрины. `null` от бэкенда значит «цена по запросу». */
export function rub(value: string | null): string {
  return value === null ? 'Цена по запросу' : `${Number(value).toLocaleString('ru-RU')} ₽`
}

/** Цена юаня — всегда с копейками: «13,80 ₽», а не «13,8 ₽». */
export function yuanPrice(value: string): string {
  const price = Number(value).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return `${price} ₽`
}

/** Время — в московском поясе явно: страницу рендерит сервер, и без пояса
 * HTML с сервера и браузер разошлись бы на три часа. */
export function moscowDateTime(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', {
    timeZone: 'Europe/Moscow', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit',
  })
}
