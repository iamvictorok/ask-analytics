/**
 * Server-Sent Events parsing for the backend's /api/chat stream.
 *
 * Works whether the DHIS2 Route passes the stream through chunk by chunk or
 * buffers the whole response: events are dispatched as soon as their block
 * is complete.
 */

/** Parse SSE text incrementally. Returns a feeder function. */
export function createSseParser(onEvent) {
    let buffer = ''
    let currentEvent = ''
    const dataLines = []
    let finished = false

    const dispatch = () => {
        if (!currentEvent && dataLines.length === 0) {
            return
        }
        const raw = dataLines.join('\n')
        let payload = raw
        try {
            payload = JSON.parse(raw)
        } catch {
            payload = raw
        }
        const type = currentEvent || 'message'
        currentEvent = ''
        dataLines.length = 0
        if (type === 'done') {
            finished = true
        }
        onEvent(type, payload)
    }

    const feed = (chunk, { flush = false } = {}) => {
        if (finished) {
            return true
        }
        buffer += chunk
        const lines = buffer.split('\n')
        buffer = flush ? '' : lines.pop() || ''
        for (const rawLine of lines) {
            const line = rawLine.endsWith('\r') ? rawLine.slice(0, -1) : rawLine
            if (line.startsWith('event:')) {
                currentEvent = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
                dataLines.push(line.slice(5).replace(/^ /, ''))
            } else if (line === '') {
                dispatch()
                if (finished) {
                    return true
                }
            }
        }
        if (flush) {
            dispatch()
        }
        return finished
    }
    return feed
}

/** Read an SSE fetch Response to the end, invoking onEvent per event. */
export async function readSseResponse(response, onEvent) {
    const feed = createSseParser(onEvent)
    if (!response.body || typeof response.body.getReader !== 'function') {
        feed(await response.text(), { flush: true })
        return
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    for (;;) {
        const { value, done } = await reader.read()
        if (done) {
            break
        }
        if (feed(decoder.decode(value, { stream: true }))) {
            reader.cancel().catch(() => {})
            return
        }
    }
    feed(decoder.decode(), { flush: true })
}
