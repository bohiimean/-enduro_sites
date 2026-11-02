export function useAuthNext() {
  const route = useRoute()
  const cart = useCart()
  const next = computed(() => safeNextPath(route.query.next, cart.pending.value ? '/checkout/request' : '/account'))
  const authLink = (path: string) => ({ path, query: { next: next.value } })
  return { next, authLink }
}
