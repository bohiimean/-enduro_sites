<script setup lang="ts">
import type { Product } from '~/composables/useApi'

const props = defineProps<{ product: Product; prefer?: 'stock' | 'order' }>()
const emit = defineEmits<{ open: [] }>()

// Главная цена — та, что выбрана фильтром, без фильтра — «в наличии», если
// байк есть. Вторая — рядом: в наличии дороже, человек выбирает сам.
const offers = computed(() => {
  const { stock, order } = props.product
  const list: { label: string; price: string | null }[] = []
  if (stock) list.push({ label: 'В наличии МСК', price: stock.price_rub })
  if (order) list.push({ label: 'Предзаказ КНР', price: order.price_rub })
  return props.prefer === 'order' ? list.reverse() : list
})

// Карточка — настоящая ссылка на страницу модели: по ней ходит поиск, её
// открывают в новой вкладке. Обычный клик вместо перехода открывает окно.
function onClick(event: MouseEvent) {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
  event.preventDefault()
  emit('open')
}
</script>

<template>
  <div class="shadow">
    <a :href="`/catalog/${product.slug}`" class="bike" @click="onClick">
      <div class="head">
        <span v-if="product.stock" class="status stock">
          <span aria-hidden="true">● </span>В наличии: {{ product.stock.qty }} шт
        </span>
        <span v-else-if="product.order" class="status order"><span aria-hidden="true">● </span>Предзаказ КНР</span>
        <span v-else class="status"><span aria-hidden="true">● </span>Нет в продаже</span>
        <span class="more" aria-hidden="true">Подробнее ↗</span>
      </div>

      <div class="body">
        <div class="photo">
          <BikePhoto :src="product.photos[0]?.url" :alt="product.title" />
        </div>
        <h3>{{ product.title }}</h3>
        <ul v-if="product.highlights.length" class="chips">
          <li v-for="item in product.highlights" :key="item">{{ item }}</li>
        </ul>
        <p class="tagline">{{ product.tagline }}</p>

        <div class="foot">
          <div v-if="offers.length" class="prices">
            <div>
              <div class="label">{{ offers[0].label }}</div>
              <div class="price">{{ rub(offers[0].price) }}</div>
            </div>
            <div v-if="offers[1]" class="alt">
              <div class="label">{{ offers[1].label }}</div>
              <div class="alt-price">{{ rub(offers[1].price) }}</div>
            </div>
          </div>
          <p v-else class="label unavailable">Сейчас не продаётся — уточните у менеджера</p>
          <span class="btn">Подробнее</span>
        </div>
      </div>
    </a>
  </div>
</template>

<style scoped>
/* Тень — фильтром на обёртке: срезанные углы карточки обрезали бы обычную. */
.shadow { height: 100%; transition: filter .3s; }
.shadow:hover { filter: drop-shadow(0 14px 18px rgb(17 24 39 / .12)); }

.bike {
  display: flex; flex-direction: column; height: 100%;
  background: #fff; border: 2px solid var(--line); color: var(--fg); text-decoration: none;
  clip-path: polygon(15px 0, 100% 0, 100% calc(100% - 15px), calc(100% - 15px) 100%, 0 100%, 0 15px);
  transition: border-color .3s;
}
.bike:hover { border-color: var(--accent); }
.bike:focus-visible { outline: 3px solid var(--accent); outline-offset: -6px; }

.head {
  display: flex; justify-content: space-between; gap: 1rem;
  padding: .75rem 1.25rem; background: var(--light); border-bottom: 1px solid var(--line);
  font: 700 .75rem/1rem var(--display); text-transform: uppercase; letter-spacing: .1em;
}
.status { color: var(--muted); }
.status.stock { color: var(--ok); }
.status.order { color: var(--accent); }
.more { color: var(--muted); white-space: nowrap; transition: color .2s; }
.bike:hover .more { color: var(--accent); }

.body { display: flex; flex-direction: column; flex: 1; padding: 1.5rem; }
.photo { height: 10rem; margin-bottom: 1rem; overflow: hidden; }
.photo :deep(img) { transition: transform .3s; }
.bike:hover .photo :deep(img) { transform: scale(1.05); }

h3 { margin: 0 0 .625rem; font-size: 1.5rem; line-height: 1.25; font-weight: 700; }
.chips { list-style: none; margin: 0 0 .75rem; padding: 0; display: flex; flex-wrap: wrap; gap: .375rem; }
.chips li {
  padding: .25rem .5rem; border: 1px solid var(--line); color: var(--muted);
  font: 600 .6875rem/1rem var(--display); text-transform: uppercase; letter-spacing: .06em;
}
.tagline { margin: 0 0 1.5rem; min-height: 2rem; font-size: .75rem; line-height: 1rem; color: var(--muted); }

.foot { margin-top: auto; padding-top: 1rem; border-top: 1px solid var(--line); }
.prices { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; margin-bottom: 1rem; }
.label { font: 400 .625rem/1rem var(--display); text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }
.price { font: 700 1.5rem/2rem var(--display); }
.alt { text-align: right; }
.alt-price { font: 600 1rem/1.5rem var(--display); color: var(--muted); }
.unavailable { margin: 0 0 1rem; font-size: .75rem; }
.btn { width: 100%; padding: .625rem 1rem; }
</style>
