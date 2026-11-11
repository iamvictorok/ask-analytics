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
