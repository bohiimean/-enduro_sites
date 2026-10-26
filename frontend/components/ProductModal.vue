<script setup lang="ts">
import type { Product } from '~/composables/useApi'

defineProps<{ product: Product }>()
const emit = defineEmits<{ close: [] }>()

const dialog = ref<HTMLElement | null>(null)
let returnFocus: HTMLElement | null = null

// Tab не уходит из окна на страницу под ним.
function keepFocusInside(event: KeyboardEvent) {
  const nodes = dialog.value?.querySelectorAll<HTMLElement>('a[href], button:not([disabled])')
  if (!nodes?.length) return
  const first = nodes[0]
  const last = nodes[nodes.length - 1]
  const active = document.activeElement
  if (event.shiftKey && (active === first || active === dialog.value)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
  else if (event.key === 'Tab') keepFocusInside(event)
}

onMounted(() => {
  returnFocus = document.activeElement as HTMLElement | null
  // Страница под окном не прокручивается; ширину пропавшей полосы прокрутки
  // возмещаем отступом, иначе вёрстка дёрнется вбок.
  const root = document.documentElement
  const scrollbar = window.innerWidth - root.clientWidth
  root.style.overflow = 'hidden'
  if (scrollbar > 0) root.style.paddingRight = `${scrollbar}px`
  window.addEventListener('keydown', onKeydown)
  dialog.value?.focus()
})

onBeforeUnmount(() => {
  document.documentElement.style.overflow = ''
  document.documentElement.style.paddingRight = ''
  window.removeEventListener('keydown', onKeydown)
  returnFocus?.focus()
})
</script>

<template>
  <div class="backdrop" @click.self="emit('close')">
    <div
      ref="dialog"
      class="dialog"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="`bike-${product.id}`"
      tabindex="-1"
    >
      <button type="button" class="close" aria-label="Закрыть" @click="emit('close')">✕</button>
      <div class="scroll">
        <ProductDetails :product="product" title-tag="h2" :title-id="`bike-${product.id}`" in-modal />
      </div>
    </div>
  </div>
</template>

<style scoped>
.backdrop {
  position: fixed; inset: 0; z-index: 50;
  display: flex; align-items: center; justify-content: center; padding: 1rem;
  background: rgb(17 24 39 / .4); backdrop-filter: blur(4px);
  animation: fade .15s ease-out;
}
.dialog {
  position: relative; display: flex; width: 100%; max-width: 48rem; max-height: 90vh;
  background: #fff; border: 1px solid var(--line);
  clip-path: polygon(15px 0, 100% 0, 100% calc(100% - 15px), calc(100% - 15px) 100%, 0 100%, 0 15px);
  animation: rise .2s ease-out;
}
.dialog:focus { outline: none; }
.scroll { flex: 1; overflow-y: auto; overscroll-behavior: contain; padding: 2rem; }
.close {
  position: absolute; top: .75rem; right: .75rem; z-index: 1;
  width: 2.5rem; height: 2.5rem; padding: 0;
  background: #fff; color: var(--muted); font-size: 1.25rem; line-height: 1;
}
.close:hover { color: var(--accent); }
.close:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }

@keyframes fade { from { opacity: 0; } }
@keyframes rise { from { opacity: 0; transform: translateY(12px); } }

@media (max-width: 640px) {
  .backdrop { padding: .5rem; }
  .dialog { max-height: calc(100dvh - 1rem); }
  .scroll { padding: 1.25rem; }
}
</style>
