/** Возвращаемся только на внутренний путь, включая после подтверждения почты. */
export function safeNextPath(value: unknown, fallback = '/account'): string {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')
    && !/[\\\u0000-\u0020]/.test(value) ? value : fallback
}
