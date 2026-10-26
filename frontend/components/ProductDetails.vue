<script setup lang="ts">
import type { Product } from '~/composables/useApi'

// Карточка байка целиком: одна и та же в окне на главной и на странице модели.
const props = withDefaults(
  defineProps<{ product: Product; titleTag?: 'h1' | 'h2'; titleId?: string; inModal?: boolean }>(),
  { titleTag: 'h1', titleId: undefined },
)

const telegram = useRuntimeConfig().public.managerTelegram

const sectionTag = computed(() => (props.titleTag === 'h1' ? 'h2' : 'h3'))
const groupTag = computed(() => (props.titleTag === 'h1' ? 'h3' : 'h4'))

const photoIndex = ref(0)
const photo = computed(() => props.product.photos[photoIndex.value])

const tag = computed(() => {
  if (props.product.stock) return 'В наличии в Москве'
  if (props.product.order) return 'Под заказ из Китая'
  return 'Нет в продаже'
})

const lead = computed(() => [props.product.powertrain_label, props.product.tagline].filter(Boolean).join(' · '))

const rateNote = computed(() => {
  const { rate, order } = props.product
  if (!rate || !order?.price_rub) return ''
  return `по курсу ${yuanPrice(rate.price_per_cny)} за юань, ${moscowDateTime(rate.fetched_at)}`
})

const facts = computed(() => {
  const { colors, documents_label: documents } = props.product
  return [
    ...(colors ? [{ label: 'Цвета', value: colors }] : []),
    ...(documents ? [{ label: 'Документы', value: documents }] : []),
  ]
})
</script>

<template>
  <article class="details">
    <div class="top">
      <div class="gallery">
        <div class="stage">
          <BikePhoto :src="photo?.url" :alt="product.title" eager />
        </div>
        <div v-if="product.photos.length > 1" class="thumbs">
          <button
            v-for="(item, index) in product.photos"
            :key="item.id"
            type="button"
            class="thumb"
            :class="{ active: index === photoIndex }"
            :aria-label="`Фото ${index + 1}`"
            :aria-pressed="index === photoIndex"
            @click="photoIndex = index"
          >
            <img :src="item.url" alt="" loading="lazy">
          </button>
        </div>
      </div>

      <div class="info">
        <span class="tag">{{ tag }}</span>
        <component :is="titleTag" :id="titleId" class="title">{{ product.title }}</component>
        <p v-if="lead" class="lead">{{ lead }}</p>

        <div class="offers">
          <div class="offer stock" :class="{ off: !product.stock }">
            <div>
              <div class="offer-name">В наличии, Москва</div>
              <div v-if="product.stock" class="offer-note">{{ product.stock.qty }} шт, можно забрать сразу</div>
            </div>
            <div class="offer-price">{{ product.stock ? rub(product.stock.price_rub) : 'Нет в наличии' }}</div>
          </div>
          <div class="offer order" :class="{ off: !product.order }">
            <div>
              <div class="offer-name">Предзаказ из Китая</div>
              <div v-if="product.order?.lead_time" class="offer-note">срок поставки {{ product.order.lead_time }}</div>
            </div>
            <div class="offer-price">{{ product.order ? rub(product.order.price_rub) : 'Не принимаем' }}</div>
          </div>
        </div>

        <!-- Корзины нет: байки на сайте не продаются, карточка ведёт к менеджеру. -->
        <a v-if="telegram" :href="`https://t.me/${telegram}`" target="_blank" rel="noopener" class="btn cta">
          Написать менеджеру
        </a>
        <p class="note">
          Покупка — через менеджера: он уточнит экземпляр, цвет и сроки.
          <template v-if="rateNote">Цена под заказ — {{ rateNote }}.</template>
        </p>
        <NuxtLink v-if="inModal" :to="`/catalog/${product.slug}`" class="permalink">Страница модели ↗</NuxtLink>
      </div>
    </div>

    <section v-if="facts.length || product.specs.length" class="specs">
      <component :is="sectionTag" class="section-title">Технические характеристики</component>
      <dl v-if="facts.length" class="spec-list">
        <div v-for="item in facts" :key="item.label" class="spec-row">
          <dt>{{ item.label }}</dt><dd>{{ item.value }}</dd>
        </div>
      </dl>
      <template v-for="group in product.specs" :key="group.title">
        <component :is="groupTag" class="group-title">{{ group.title }}</component>
        <dl class="spec-list">
          <div v-for="item in group.items" :key="item.label" class="spec-row">
            <dt>{{ item.label }}</dt><dd>{{ item.value }}</dd>
          </div>
        </dl>
      </template>
    </section>

    <section v-if="product.description" class="about">
      <component :is="sectionTag" class="section-title">Описание</component>
      <p>{{ product.description }}</p>
    </section>
  </article>
</template>

<style scoped>
.details { display: grid; gap: 2rem; }
.top { display: grid; gap: 2rem; }

.stage {
  height: 16rem; padding: 1.5rem; background: var(--light);
  clip-path: polygon(15px 0, 100% 0, 100% calc(100% - 15px), calc(100% - 15px) 100%, 0 100%, 0 15px);
}
.thumbs { display: flex; gap: .5rem; margin-top: .75rem; overflow-x: auto; }
.thumb {
  flex: none; width: 4.5rem; height: 3.5rem; padding: .25rem;
  background: var(--light); border: 2px solid transparent;
}
.thumb.active { border-color: var(--accent); }
.thumb img { width: 100%; height: 100%; object-fit: contain; mix-blend-mode: multiply; }

.info { display: grid; gap: 1rem; justify-items: start; align-content: center; }
.tag {
  padding: .125rem .75rem; background: var(--accent); color: #fff;
  font: 700 .75rem/1rem var(--display); text-transform: uppercase; letter-spacing: .1em;
}
.title { margin: 0; font-size: 2.25rem; line-height: 2.5rem; font-weight: 700; }
.lead { margin: 0; font-size: .875rem; line-height: 1.6; color: var(--muted); }

.offers { display: grid; gap: .5rem; width: 100%; padding-top: .5rem; }
.offer {
  display: flex; justify-content: space-between; align-items: center; gap: 1rem;
  padding: .75rem; border: 2px solid var(--line);
}
.offer.stock { border-color: #10b981; background: #ecfdf5; }
.offer.order { border-color: var(--accent); background: #fff7ed; }
.offer.off { border-color: var(--line); background: #fff; opacity: .5; }
.offer-name { font: 700 .75rem/1rem var(--display); text-transform: uppercase; letter-spacing: .05em; }
.offer.order .offer-name { color: var(--accent-ink); }
.offer-note { font-size: .75rem; color: var(--muted); }
.offer-price { font: 700 1.25rem/1.75rem var(--display); white-space: nowrap; text-align: right; }

.cta { width: 100%; padding: .875rem 1rem; font-size: 1rem; }
.note { margin: 0; font-size: .75rem; line-height: 1.5; color: var(--muted); }
.permalink {
  font: 600 .75rem/1 var(--display); text-transform: uppercase; letter-spacing: .1em;
  color: var(--muted); text-decoration: none;
}
.permalink:hover { color: var(--accent-ink); }

.specs, .about { padding-top: 1.5rem; border-top: 1px solid var(--line); }
/* Уровень заголовков в окне и на странице разный, вид — один. */
.section-title { margin: 0 0 1rem; font: 700 1.25rem/1.4 var(--display); text-transform: uppercase; }
.group-title {
  margin: 1.25rem 0 .25rem; color: var(--accent-ink);
  font: 600 .8125rem/1.25rem var(--display); text-transform: uppercase; letter-spacing: .1em;
}
.spec-list { display: grid; column-gap: 1.5rem; margin: 0; }
.spec-row {
  display: flex; justify-content: space-between; gap: 1rem;
  padding: .5rem 0; border-bottom: 1px solid var(--line); font-size: .8125rem;
}
.spec-row dt { color: var(--muted); text-transform: uppercase; }
.spec-row dd { margin: 0; font-weight: 700; text-align: right; }
.about p { margin: 0; max-width: 48rem; white-space: pre-line; font-size: .875rem; color: var(--muted); }

@media (min-width: 768px) {
  .top { grid-template-columns: 1fr 1fr; align-items: center; }
  .stage { height: 18rem; }
  .spec-list { grid-template-columns: 1fr 1fr; }
}
</style>
