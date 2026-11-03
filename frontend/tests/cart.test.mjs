import assert from 'node:assert/strict'
import { webcrypto } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { stripTypeScriptTypes } from 'node:module'
import { test } from 'node:test'
import vm from 'node:vm'

const source = stripTypeScriptTypes(readFileSync(new URL('../composables/useCart.ts', import.meta.url), 'utf8'))
  .replaceAll('import.meta.client', 'true').replaceAll('export ', '')
const plain = (value) => JSON.parse(JSON.stringify(value))
const bike = { id: 1, stock: { qty: 2, price_rub: '250000' }, order: { price_rub: '230000' } }
const goods = { id: 1, price_rub: null, availability: 'order' }
function environment(storage = new Map(), unavailable = false, http = false) {
  const states = new Map()
  const context = vm.createContext({
    crypto: http ? { getRandomValues: webcrypto.getRandomValues.bind(webcrypto) } : webcrypto,
    localStorage: {
      getItem: (key) => { if (unavailable) throw new Error('unavailable'); return storage.get(key) ?? null },
      setItem: (key, value) => { if (unavailable) throw new Error('unavailable'); storage.set(key, value) },
    },
    useState: (key, init) => { if (!states.has(key)) states.set(key, { value: init() }); return states.get(key) },
    computed: (getter) => ({ get value() { return getter() } }),
    isGoods: (product) => 'price_rub' in product,
  })
  vm.runInContext(source + '\nglobalThis.cart = useCart();', context)
  return { cart: context.cart, storage }
}

test('HTTP without randomUUID can save the cart and submit a stable UUID v4', () => {
  const { cart, storage } = environment(new Map(), false, true)
  cart.add(goods, 'order')
  const key = cart.submissionKey.value
  assert.match(key, /^[\da-f]{8}-[\da-f]{4}-4[\da-f]{3}-[89ab][\da-f]{3}-[\da-f]{12}$/)
  cart.beginCheckout()
  assert.equal(cart.submissionKey.value, key)
  const restored = environment(storage, false, true).cart
  restored.initialize()
  assert.equal(restored.submissionKey.value, key)
  cart.quantity(cart.items.value[0], 2)
  assert.notEqual(cart.submissionKey.value, key)
})

test('bike stock, bike preorder and goods with same id are distinct rows', () => {
  const { cart } = environment()
  assert.equal(cart.add(bike, 'stock'), '')
  cart.add(bike, 'order')
  cart.add(goods, 'order')
  cart.add(bike, 'stock')
  assert.equal(cart.items.value.length, 3)
  assert.equal(cart.count.value, 4)
  assert.notEqual(cart.add(bike, 'stock'), '')
  assert.equal(cart.count.value, 4)
})

test('quantity, checkout intent and retry key survive reload without saving contacts or product data', () => {
  const { cart, storage } = environment()
  cart.add({ ...goods, title: 'Battery', name: 'private', phone: 'private' }, 'order')
  cart.quantity(cart.items.value[0], 3)
  cart.beginCheckout()
  const key = cart.submissionKey.value
  cart.beginCheckout()
  assert.equal(cart.submissionKey.value, key)
  const reloaded = environment(storage).cart
  reloaded.initialize()
  assert.equal(reloaded.count.value, 3)
  assert.equal(reloaded.pending.value, true)
  assert.equal(reloaded.submissionKey.value, key)
  assert.deepEqual(plain(reloaded.items.value), [{ kind: 'goods', product_id: 1, offer: 'order', quantity: 3 }])
  assert.ok(![...storage.values()].join('').includes('private'))
})

test('successful submission clears exactly the submitted cart', () => {
  const { cart, storage } = environment()
  cart.add(goods, 'order')
  cart.beginCheckout()
  cart.completed(cart.submissionKey.value)
  assert.equal(cart.count.value, 0)
  assert.equal(cart.pending.value, false)
  const reloaded = environment(storage).cart
  reloaded.initialize()
  assert.equal(reloaded.count.value, 0)
})

test('response from an older submission never clears newly selected items', () => {
  const { cart } = environment()
  cart.add(goods, 'order')
  const oldKey = cart.submissionKey.value
  cart.add(bike, 'order')
  assert.notEqual(cart.submissionKey.value, oldKey)
  cart.completed(oldKey)
  assert.equal(cart.count.value, 2)
})

test('invalid stored data is discarded and duplicate rows are not restored', () => {
  const row = { kind: 'bike', product_id: 1, offer: 'order', quantity: 2 }
  const storage = new Map([['skl-cart-v1', JSON.stringify({ items: [row, row, { ...row, kind: 'foreign' }, { ...row, quantity: 0 }, { ...row, product_id: '2' }] })]])
  const { cart } = environment(storage)
  cart.initialize()
  assert.deepEqual(plain(cart.items.value), [row])
})

test('blocked storage leaves an actionable in-memory cart and reports persistence failure', () => {
  const { cart } = environment(new Map(), true)
  assert.equal(cart.add(goods, 'order'), '')
  assert.equal(cart.count.value, 1)
  assert.equal(cart.storageFailed.value, true)
})

test('quantity bounds, removal and unavailable offers are enforced', () => {
  const { cart } = environment()
  assert.notEqual(cart.add(goods, 'stock'), '')
  cart.add(goods, 'order')
  cart.quantity(cart.items.value[0], 0)
  cart.quantity(cart.items.value[0], 100)
  assert.equal(cart.count.value, 1)
  cart.quantity(cart.items.value[0], 99)
  assert.equal(cart.count.value, 99)
  cart.remove(cart.items.value[0])
  assert.equal(cart.count.value, 0)
})

const nextSource = stripTypeScriptTypes(readFileSync(new URL('../utils/authNext.ts', import.meta.url), 'utf8')).replaceAll('export ', '')
const nextContext = vm.createContext({})
vm.runInContext(nextSource + '\nglobalThis.next = safeNextPath;', nextContext)
test('auth return path preserves checkout and refuses external and ambiguous destinations', () => {
  assert.equal(nextContext.next('/checkout/request'), '/checkout/request')
  for (const value of ['https://evil.example', '//evil.example', '/\\evil.example', '/\nevil', undefined]) {
    assert.equal(nextContext.next(value), '/account')
  }
})


test('a malformed stored submission key is renewed before checkout', () => {
  const storage = new Map([['skl-cart-v1', JSON.stringify({
    items: [{ kind: 'goods', product_id: 1, offer: 'order', quantity: 1 }],
    submissionKey: '-'.repeat(36),
  })]])
  const { cart } = environment(storage)
  cart.initialize()
  cart.beginCheckout()
  assert.match(cart.submissionKey.value, /^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i)
})

test('delivery and payment survive auth reload and invalidate the retry key when changed', () => {
  const { cart, storage } = environment()
  cart.add(bike, 'stock')
  const before = cart.submissionKey.value
  cart.setOptions('Казань', 'usdt')
  assert.notEqual(cart.submissionKey.value, before)
  const same = cart.submissionKey.value
  cart.setOptions('Казань', 'usdt')
  assert.equal(cart.submissionKey.value, same)
  const restored = environment(storage).cart
  restored.initialize()
  assert.equal(restored.city.value, 'Казань')
  assert.equal(restored.paymentMethod.value, 'usdt')
  restored.completed(same)
  assert.equal(restored.city.value, '')
  assert.equal(restored.paymentMethod.value, '')
})

test('switching offers merges rows and refuses stock overflow without losing items', () => {
  const { cart } = environment()
  cart.add(bike, 'stock')
  cart.add(bike, 'order')
  assert.equal(cart.changeOffer(cart.items.value[1], bike, 'stock'), '')
  assert.equal(cart.items.value.length, 1)
  assert.equal(cart.items.value[0].quantity, 2)
  cart.add(bike, 'order')
  assert.ok(cart.changeOffer(cart.items.value[1], bike, 'stock'))
  assert.equal(cart.items.value.length, 2)
  assert.equal(cart.count.value, 3)
})
