// Один таймер на вкладку. Подписки появляются только после mount (без SSR).
const priceRefreshers = new Set<() => Promise<void>>()
let priceTimer: ReturnType<typeof setInterval> | undefined

function refreshVisiblePrices() {
  if (document.visibilityState !== 'visible') return
  for (const refresh of priceRefreshers) void refresh()
}

export function useVisibleRefresh(callback: () => Promise<unknown>, immediate = true) {
  const failed = ref(false)
  let running = false
  let active = false
  async function refresh() {
    if (!active || running || document.visibilityState !== 'visible') return
    running = true
    try {
      await callback()
      failed.value = false
    } catch {
      // Последние данные остаются на экране; следующий тик повторит запрос.
      failed.value = true
    } finally { running = false }
  }
  onMounted(() => {
    active = true
    priceRefreshers.add(refresh)
    if (!priceTimer) {
      priceTimer = setInterval(refreshVisiblePrices, 30_000)
      document.addEventListener('visibilitychange', refreshVisiblePrices)
    }
    if (immediate) void refresh()
  })
  onBeforeUnmount(() => {
    active = false
    priceRefreshers.delete(refresh)
    if (!priceRefreshers.size) {
      clearInterval(priceTimer)
      priceTimer = undefined
      document.removeEventListener('visibilitychange', refreshVisiblePrices)
    }
  })
  return { failed, refresh }
}
