/**
 * Route code lookup. Non-secret configuration only:
 *   1. UserDataStore  ask-analytics/settings  (a user's own override)
 *   2. DataStore      ask-analytics/settings  (instance default set by an admin;
 *                     the namespace is reserved for this app in its manifest)
 *   3. DEFAULT_ROUTE_CODE
 */
import { DEFAULT_ROUTE_CODE, isValidRouteCode } from './routeClient.js'

export const NAMESPACE = 'ask-analytics'
export const SETTINGS_KEY = 'settings'

const read = async (engine, resource) => {
    try {
        const res = await engine.query({ s: { resource } })
        return res?.s || null
    } catch {
        return null // 404 = not set yet
    }
}

export async function loadRouteCode(engine) {
    const user = await read(engine, `userDataStore/${NAMESPACE}/${SETTINGS_KEY}`)
    if (isValidRouteCode(user?.routeCode)) {
        return { routeCode: user.routeCode, source: 'user' }
    }
    const global = await read(engine, `dataStore/${NAMESPACE}/${SETTINGS_KEY}`)
    if (isValidRouteCode(global?.routeCode)) {
        return { routeCode: global.routeCode, source: 'instance' }
    }
    return { routeCode: DEFAULT_ROUTE_CODE, source: 'default' }
}

const upsert = async (engine, store, data) => {
    const resource = `${store}/${NAMESPACE}/${SETTINGS_KEY}`
    try {
        await engine.mutate({ resource, type: 'update', data })
    } catch {
        await engine.mutate({ resource, type: 'create', data })
    }
}

export const saveUserRouteCode = (engine, routeCode) =>
    upsert(engine, 'userDataStore', { routeCode })

export const saveInstanceRouteCode = (engine, routeCode) =>
    upsert(engine, 'dataStore', { routeCode })
