<script setup lang="ts">
import type { Paginated, Product } from '~/composables/useApi'

// Главная — каталог, по макету skl_moto.html.
definePageMeta({ fullWidth: true })

useHead({ title: 'SKL MOTO | Официальный дилер', titleTemplate: null })
useSeoMeta({
  description: 'Эндуро и электро-эндуро: в наличии в Москве и под заказ напрямую с заводов Китая. '
    + 'Договор и оплата в рублях.',
})

const route = useRoute()
const router = useRouter()
const apiBase = useApiBase()

const AVAILABILITY = [
  { value: undefined, label: 'Все модели', dot: '' },
  { value: 'stock', label: 'В наличии (МСК)', dot: 'stock' },
  { value: 'order', label: 'Предзаказ (КНР)', dot: 'order' },
] as const
const POWERTRAIN = [
  { value: 'ice', label: 'ДВС' },
  { value: 'electric', label: 'Электро' },
] as const

function fromQuery<T extends string>(key: string, allowed: readonly T[]): T | undefined {
  const value = route.query[key]
  return allowed.includes(value as T) ? (value as T) : undefined
}

// Фильтры живут в адресе: ссылку с ними можно переслать, поиск видит каждую
// выборку. Незнакомое значение — весь каталог, как и на бэкенде. Каждый
// фильтр — отдельный computed со строкой, чтобы открытие окна байка (тоже
// параметр адреса) не перезапрашивало каталог.
const availability = computed(() => fromQuery('availability', ['stock', 'order'] as const))
const powertrain = computed(() => fromQuery('powertrain', ['ice', 'electric'] as const))

function filterLink(key: 'availability' | 'powertrain', value?: string) {
  return { query: { ...route.query, bike: undefined, [key]: value } }
}

const { data, error } = await useApiFetch<Paginated<Product>>('/catalog/products/', {
  query: { availability, powertrain },
})
const { data: terms } = useCatalogTerms()

const markup = computed(() => {
  const value = terms.value?.order_markup_percent
  return value ? Number(value).toLocaleString('ru-RU') : ''
})

// Бэкенд отдаёт каталог страницами по 20 — дальше догружаем кнопкой.
const more = ref<Product[]>([])
const loadingMore = ref(false)
const moreFailed = ref(false)
watch(data, () => {
  more.value = []
  moreFailed.value = false
})
const products = computed(() => [...(data.value?.results ?? []), ...more.value])
const hasMore = computed(() => products.value.length < (data.value?.count ?? 0))

async function loadMore() {
  const filters = { availability: availability.value, powertrain: powertrain.value }
  loadingMore.value = true
  moreFailed.value = false
  try {
    const page = await $fetch<Paginated<Product>>('/catalog/products/', {
      baseURL: apiBase, query: { ...filters, offset: products.value.length },
    })
    // Пока ждали, фильтр могли сменить — тогда эта страница уже от другой выборки.
    if (filters.availability === availability.value && filters.powertrain === powertrain.value) {
      more.value.push(...page.results)
    }
  } catch {
    moreFailed.value = true
  } finally {
    loadingMore.value = false
  }
}

// В шапке — первое фото каталога. Запоминается на всю сессию, чтобы картинка
// не менялась от переключения фильтров.
const heroPhoto = useState<string | null>(
  'hero-photo',
  () => data.value?.results.find((product) => product.photos.length)?.photos[0].url ?? null,
)

// Окно байка тоже в адресе (?bike=…): «назад» на телефоне закрывает окно,
// а не уводит с сайта.
const selected = computed(() => {
  const slug = route.query.bike
  return typeof slug === 'string' ? products.value.find((product) => product.slug === slug) ?? null : null
})

let openedHere = false
watch(() => route.query.bike, (slug) => {
  if (!slug) openedHere = false
})

function openBike(product: Product) {
  openedHere = true
  router.push({ query: { ...route.query, bike: product.slug } })
}

function closeBike() {
  if (openedHere) router.back()
  else router.replace({ query: { ...route.query, bike: undefined } })
}

// Фильтр сменили, проскроллив выдачу вниз, — возвращаем к её началу.
const catalog = ref<HTMLElement | null>(null)
watch([availability, powertrain], () => {
  if (catalog.value && catalog.value.getBoundingClientRect().top < 0) {
    catalog.value.scrollIntoView({ block: 'start' })
  }
})
</script>

<template>
  <div>
    <section class="hero">
      <div class="container hero-row">
        <div class="hero-text">
          <span class="hero-tag">Импорт без посредников</span>
          <h1>Эндуро и электро.<br><span>Прямо с завода.</span></h1>
          <p>
            Забирай технику из наличия в Москве или оформляй прямой предзаказ из
            Китая<template v-if="markup"> с фиксированной наценкой {{ markup }}%</template>.
            Прозрачный договор и оплата в рублях.
          </p>
        </div>
        <div class="hero-art">
          <img v-if="heroPhoto" :src="heroPhoto" alt="" class="hero-photo">
          <div v-else class="hero-mark" aria-hidden="true">
            <span class="mark-skl">SKL</span>
            <span class="mark-moto">MOTO</span>
          </div>
        </div>
      </div>
    </section>

    <nav class="filters" aria-label="Фильтры каталога">
      <div class="container filters-row">
        <div class="filter-group">
          <NuxtLink
            v-for="option in AVAILABILITY"
            :key="option.label"
            :to="filterLink('availability', option.value)"
            class="tab"
            :class="{ active: availability === option.value }"
            :aria-current="availability === option.value ? 'true' : undefined"
          >
            <span v-if="option.dot" class="dot" :class="option.dot" aria-hidden="true">●</span>{{ option.label }}
          </NuxtLink>
        </div>
        <div class="filter-group">
          <!-- Тип — переключатель: повторное нажатие снимает фильтр. -->
          <NuxtLink
            v-for="option in POWERTRAIN"
            :key="option.value"
            :to="filterLink('powertrain', powertrain === option.value ? undefined : option.value)"
            class="tab"
            :class="{ active: powertrain === option.value }"
            :aria-current="powertrain === option.value ? 'true' : undefined"
          >
            {{ option.label }}
          </NuxtLink>
        </div>
      </div>
    </nav>

    <section ref="catalog" class="container catalog" aria-labelledby="catalog-title">
      <h2 id="catalog-title" class="sr-only">Модели</h2>

      <p v-if="error" class="empty">Каталог не загрузился. Обновите страницу через минуту.</p>

      <div v-else-if="!products.length" class="empty">
        <template v-if="availability || powertrain">
          <p>Под эти условия байков сейчас нет.</p>
          <NuxtLink :to="{ query: {} }" class="btn btn-outline">Показать все модели</NuxtLink>
        </template>
        <p v-else>Каталог скоро появится — а пока спросите менеджера, что есть в наличии.</p>
      </div>

      <template v-else>
        <ul class="cards">
          <li v-for="product in products" :key="product.id">
            <ProductCard :product="product" :prefer="availability" @open="openBike(product)" />
          </li>
        </ul>
        <div v-if="hasMore" class="more">
          <button type="button" class="btn btn-outline" :disabled="loadingMore" @click="loadMore">
            {{ loadingMore ? 'Загружаем…' : 'Показать ещё' }}
          </button>
          <p v-if="moreFailed" class="err">Не получилось загрузить — попробуйте ещё раз.</p>
        </div>
      </template>
    </section>

    <ProductModal v-if="selected" :key="selected.slug" :product="selected" @close="closeBike" />
  </div>
</template>

<style scoped>
.hero { background: var(--light); border-bottom: 1px solid var(--line); overflow: hidden; }
.hero-row { display: grid; gap: 3rem; align-items: center; padding-top: 4rem; padding-bottom: 4rem; }
.hero-text { display: grid; gap: 1.5rem; justify-items: start; }
.hero-tag {
  padding: .25rem .75rem; background: var(--accent); color: #fff;
  font: 700 .75rem/1rem var(--display); text-transform: uppercase; letter-spacing: .1em;
  clip-path: polygon(10px 0, 100% 0, 100% 100%, 0 100%, 0 10px);
}
h1 { margin: 0; font-size: 3rem; line-height: 1; letter-spacing: -.025em; }
h1 span { color: var(--accent); }
.hero-text p { margin: 0; max-width: 28rem; font-size: .875rem; line-height: 1.6; color: var(--muted); }

.hero-art { display: flex; align-items: center; justify-content: center; height: 16rem; }
.hero-photo { width: 100%; height: 100%; object-fit: contain; mix-blend-mode: multiply; transition: transform .5s; }
.hero-photo:hover { transform: scale(1.05); }
.hero-mark { display: flex; flex-direction: column; align-items: center; gap: .75rem; user-select: none; }
.mark-skl {
  padding: 0 2.5rem; background: var(--accent); color: #fff; transform: skewX(-12deg);
  font: italic 700 clamp(5rem, 11vw, 9rem)/1.1 var(--display);
}
.mark-moto {
  margin-right: -.3em; letter-spacing: .3em; color: transparent; -webkit-text-stroke: 2px var(--fg);
  font: 700 clamp(3rem, 7vw, 5.5rem)/1 var(--display);
}

.filters {
  position: sticky; top: var(--header-h); z-index: 30;
  background: #fff; border-bottom: 1px solid var(--line); box-shadow: 0 1px 2px rgb(0 0 0 / .05);
}
.filters-row {
  display: flex; justify-content: space-between; gap: .75rem 2rem;
  padding-top: 1rem; padding-bottom: 1rem; overflow-x: auto; scrollbar-width: none;
}
.filters-row::-webkit-scrollbar { display: none; }
.filter-group { display: flex; gap: .75rem; flex: none; }
.tab {
  flex: none; display: inline-flex; align-items: center; white-space: nowrap;
  padding: .5rem 1.5rem; background: #fff; color: var(--fg); border: 2px solid var(--line);
  font: 400 1rem/1.5rem var(--display); text-transform: uppercase; letter-spacing: .1em; text-decoration: none;
  clip-path: polygon(10px 0, 100% 0, 100% 100%, 0 100%, 0 10px);
  transition: border-color .15s;
}
.tab:hover { border-color: var(--accent); }
.tab.active { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 700; }
.tab:focus-visible { outline: 2px solid var(--accent); outline-offset: -6px; }
.tab.active:focus-visible { outline-color: #fff; }
.dot { margin-right: .5rem; }
.dot.stock { color: #10b981; }
.dot.order { color: var(--accent); }
.tab.active .dot { color: #fff; }

/* Отступ сверху — под липкую шапку и строку фильтров. */
.catalog { padding-top: 3rem; padding-bottom: 4rem; scroll-margin-top: calc(var(--header-h) + 4.75rem); }
.cards { list-style: none; margin: 0; padding: 0; display: grid; gap: 2rem; }
.more { display: grid; justify-items: center; gap: .75rem; margin-top: 2.5rem; }
.empty { display: grid; justify-items: center; gap: 1rem; margin: 0; padding: 3rem 0; text-align: center; color: var(--muted); }
.empty p { margin: 0; }

@media (min-width: 768px) {
  .cards { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 1024px) {
  .hero-row { grid-template-columns: 1fr 1fr; padding-top: 6rem; padding-bottom: 6rem; }
  h1 { font-size: 4.5rem; }
  .hero-art { height: 24rem; }
  .cards { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 640px) {
  .hero-row { gap: 2rem; padding-top: 2.5rem; padding-bottom: 2.5rem; }
  h1 { font-size: 2.5rem; }
  .hero-art { height: 12rem; }
  /* Логотип-заглушка на телефоне только отодвигал бы каталог — он и так в шапке. */
  .hero-art:has(.hero-mark) { display: none; }
  .tab { padding: .375rem 1rem; font-size: .875rem; }
  .filters-row { padding-top: .75rem; padding-bottom: .75rem; }
  .catalog { padding-top: 2rem; }
}
</style>
