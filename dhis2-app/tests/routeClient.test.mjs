import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
    routeUrl,
    isValidRouteCode,
    describeRouteError,
    DEFAULT_ROUTE_CODE,
} from '../src/lib/routeClient.js'
import { createSseParser } from '../src/lib/sse.js'

test('route URLs go through /api/routes/<code>/run/', () => {
    assert.equal(
        routeUrl('https://dhis2.example.org', 'ask-analytics', 'api/chat'),
        'https://dhis2.example.org/api/routes/ask-analytics/run/api/chat'
    )
    assert.equal(
        routeUrl('https://dhis2.example.org/', 'x', '/health'),
        'https://dhis2.example.org/api/routes/x/run/health'
    )
})

test('route codes are validated', () => {
    assert.ok(isValidRouteCode(DEFAULT_ROUTE_CODE))
    assert.ok(!isValidRouteCode('../evil'))
    assert.ok(!isValidRouteCode(''))
    assert.throws(() => routeUrl('https://x', 'a/b', 'health'))
})

test('route errors are explained', () => {
    assert.match(describeRouteError(404), /Route was not found/)
    assert.match(describeRouteError(504), /60 seconds/)
})

test('SSE parser handles split chunks and done', () => {
    const events = []
    const feed = createSseParser((t, d) => events.push([t, d]))
    feed('event: token\ndata: {"te')
    feed('xt":"Hi"}\n\nevent: done\ndata: {}\n\nevent: token\ndata: {"text":"x"}\n\n')
    assert.deepEqual(events, [
        ['token', { text: 'Hi' }],
        ['done', {}],
    ])
})

test('SSE parser flushes a buffered body', () => {
    const events = []
    createSseParser((t, d) => events.push(t))(
        'event: token\ndata: {"text":"a"}\n\nevent: done\ndata: {}',
        { flush: true }
    )
    assert.deepEqual(events, ['token', 'done'])
})

test('first question in a new conversation is not aborted (regression)', async () => {
    // newConversation() aborts the in-flight request; send() must create its
    // AbortController only after awaiting it, or the first question is never sent.
    const { readFile } = await import('node:fs/promises')
    const src = await readFile(new URL('../src/App.jsx', import.meta.url), 'utf8')
    const send = src.slice(src.indexOf('const send = useCallback'))
    const awaitNew = send.indexOf('await newConversation()')
    const newCtrl = send.indexOf('new AbortController()')
    assert.ok(awaitNew > 0 && newCtrl > awaitNew)
})
