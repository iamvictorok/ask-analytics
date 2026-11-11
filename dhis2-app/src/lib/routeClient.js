/**
 * All calls to the assistant backend go through a DHIS2 Route:
 *   <DHIS2>/api/routes/<routeCode>/run/<backend path>
 *
 * The browser only ever talks to its own DHIS2 server, with the user's
 * existing session cookie. The backend URL and its shared key live in the
 * Route configuration on the server (encrypted), never in this bundle.
 */

export const DEFAULT_ROUTE_CODE = 'ask-analytics'

const ROUTE_CODE_RE = /^[A-Za-z0-9_-]{1,50}$/

export const isValidRouteCode = (code) => typeof code === 'string' && ROUTE_CODE_RE.test(code)

export function routeUrl(baseUrl, routeCode, path) {
    if (!isValidRouteCode(routeCode)) {
        throw new Error(`Invalid route code "${routeCode}"`)
    }
    const base = String(baseUrl || '').replace(/\/+$/, '')
    const sub = String(path || '').replace(/^\/+/, '')
    const rel = `${base}/api/routes/${encodeURIComponent(routeCode)}/run/${sub}`
    const origin = typeof window !== 'undefined' ? window.location.href : 'http://localhost/'
    return new URL(rel, origin).toString()
}

export class RouteError extends Error {
    constructor(status, message) {
        super(message)
        this.status = status
    }
}

export function describeRouteError(status) {
    switch (status) {
        case 401:
            return 'The assistant backend refused the request. The Route key and the backend ROUTE_SHARED_KEY probably do not match.'
        case 403:
            return "You are not allowed to run the assistant Route. Ask an administrator to add your role's authority to the Route."
        case 404:
            return 'The assistant Route was not found. Check the Route code in Settings, or ask an administrator to create it in Route Manager.'
        case 429:
            return 'Too many requests. Please wait a moment and try again.'
        case 502:
        case 503:
            return 'The assistant backend is unreachable or returned an error.'
        case 504:
            return 'The assistant backend took too long to answer. An administrator can raise the Route response timeout (up to 60 seconds).'
        default:
            return `The request failed (HTTP ${status}).`
    }
}

export function createRouteClient(baseUrl, routeCode) {
    const request = async (path, { method = 'GET', body, signal, accept } = {}) => {
        const headers = { Accept: accept || 'application/json' }
        if (body !== undefined) {
            headers['Content-Type'] = 'application/json'
        }
        const res = await fetch(routeUrl(baseUrl, routeCode, path), {
            method,
            credentials: 'include',
            headers,
            body: body === undefined ? undefined : JSON.stringify(body),
            signal,
        })
        if (!res.ok) {
            throw new RouteError(res.status, describeRouteError(res.status))
        }
        return res
    }
    return {
        request,
        getJson: async (path) => (await request(path)).json(),
        postJson: async (path, body = {}) => (await request(path, { method: 'POST', body })).json(),
    }
}
