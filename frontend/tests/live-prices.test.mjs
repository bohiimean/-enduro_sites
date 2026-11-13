import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { stripTypeScriptTypes } from 'node:module'
import { test } from 'node:test'
import vm from 'node:vm'

const source = stripTypeScriptTypes(readFileSync(new URL('../composables/useVisibleRefresh.ts', import.meta.url), 'utf8'))
  .replaceAll('export ', '')
const settle = () => new Promise((resolve) => setImmediate(resolve))

function environment() {
  const timers = new Map()
  const listeners = new Map()
  let mount, unmount
  const document = {
    visibilityState: 'visible',
    addEventListener: (key, fn) => listeners.set(key, fn),
    removeEventListener: (key) => listeners.delete(key),
  }
  const context = vm.createContext({
    document, ref: (value) => ({ value }),
    onMounted: (fn) => { mount = fn }, onBeforeUnmount: (fn) => { unmount = fn },
    setInterval: (fn, ms) => { assert.equal(ms, 30000); timers.set(1, fn); return 1 },
    clearInterval: (id) => timers.delete(id),
  })
  vm.runInContext(source + '\nglobalThis.subscribe = useVisibleRefresh;', context)
  return {
    timers, listeners, document,
    add(callback) {
      const result = context.subscribe(callback)
      const destroy = unmount
      mount()
      return { ...result, destroy }
    },
    tick() { for (const fn of timers.values()) fn() },
    visibility(state) { document.visibilityState = state; listeners.get('visibilitychange')?.() },
  }
}

test('one 30-second timer updates subscribers, pauses hidden tabs and resumes immediately', async () => {
  const env = environment()
  let first = 0, second = 0
  const a = env.add(async () => { first++ })
  const b = env.add(async () => { second++ })
  await settle()
  assert.equal(env.timers.size, 1)
  assert.equal(first, 1)
  env.tick(); await settle()
  assert.equal(first, 2)
  assert.equal(second, 2)
  env.visibility('hidden'); env.tick(); await settle()
  assert.equal(first, 2)
  env.visibility('visible'); await settle()
  assert.equal(first, 3)
  a.destroy()
  env.tick(); await settle()
  assert.equal(first, 3)
  assert.equal(second, 4)
  b.destroy()
  assert.equal(env.timers.size, 0)
  assert.equal(env.listeners.size, 0)
})

test('slow requests do not overlap and failures retry without unhandled rejections', async () => {
  const env = environment()
  let resolve, calls = 0
  const result = env.add(() => { calls++; return new Promise((r) => { resolve = r }) })
  env.tick(); env.tick()
  assert.equal(calls, 1)
  resolve(); await settle()
  result.destroy()
  let fail = true
  const retry = env.add(async () => { if (fail) throw new Error('offline') })
  await settle()
  assert.equal(retry.failed.value, true)
  fail = false
  env.tick(); await settle()
  assert.equal(retry.failed.value, false)
  retry.destroy()
})
