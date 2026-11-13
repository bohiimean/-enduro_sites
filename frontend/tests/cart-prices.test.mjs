import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { stripTypeScriptTypes } from 'node:module'
import { test } from 'node:test'
import vm from 'node:vm'
import { computed, ref, watch, nextTick } from 'vue'

const source = stripTypeScriptTypes(readFileSync(new URL('../composables/useCartCatalog.ts', import.meta.url), 'utf8'))
  .replaceAll('export ', '')
const line = (id) => ({ kind: 'bike', product_id: id, offer: 'order', quantity: 1 })
const bike = (price) => ({ id: 1, order: { price_rub: price }, stock: null })
const settle = () => new Promise((resolve) => setImmediate(resolve))

function environment(fetch) {
  let mount, poll
  const items = ref([line(1)])
  const context = vm.createContext({
    ref, computed, watch, $fetch: fetch, useApiBase: () => '/api/v1',
    isGoods: (product) => 'price_rub' in product,
    useCart: () => ({ items, initialize() {} }),
    onMounted: (fn) => { mount = fn },
    useVisibleRefresh: (fn) => { poll = fn },
  })
  vm.runInContext(source + '\nglobalThis.catalog = useCartCatalog();', context)
  mount()
  return { catalog: context.catalog, items, poll, context }
}

test('background price refresh keeps cart visible and preserves the last price on network failure', async () => {
  const env = environment(async () => bike('100000'))
  await settle()
  assert.equal(env.catalog.total.value, '100000.00')
  let resolve
  env.context.$fetch = () => new Promise((r) => { resolve = r })
  const pending = env.poll()
  assert.equal(env.catalog.loading.value, false)
  assert.equal(env.catalog.total.value, '100000.00')
  resolve(bike('110000')); await pending
  assert.equal(env.catalog.total.value, '110000.00')
  env.context.$fetch = async () => { throw new Error('offline') }
  await env.poll()
  assert.equal(env.catalog.total.value, '110000.00')
  assert.equal(env.catalog.valid.value, false)
  assert.ok(env.catalog.error.value)
  env.context.$fetch = async () => bike('120000')
  await env.poll()
  assert.equal(env.catalog.total.value, '120000.00')
  assert.equal(env.catalog.valid.value, true)
})

test('a late refresh cannot overwrite a changed cart; deleted products become unavailable', async () => {
  const env = environment(async () => bike('100000'))
  await settle()
  let resolve
  env.context.$fetch = () => new Promise((r) => { resolve = r })
  const old = env.poll()
  env.context.$fetch = async () => bike('200000')
  env.items.value = [line(2)]
  await nextTick(); await settle()
  resolve(bike('90000')); await old
  assert.equal(env.catalog.total.value, '200000.00')
  env.context.$fetch = async () => { throw { statusCode: 404 } }
  await env.poll()
  assert.equal(env.catalog.valid.value, false)
  assert.equal(env.catalog.total.value, null)
})
