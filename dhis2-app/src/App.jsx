import { useConfig, useDataEngine, useDataQuery } from '@dhis2/app-runtime'
import {
    Button,
    CenteredContent,
    CircularLoader,
    IconSettings24,
    NoticeBox,
    SingleSelectField,
    SingleSelectOption,
    TextArea,
    Chip,
} from '@dhis2/ui'
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import styles from './App.module.css'
import ConversationList from './components/ConversationList.jsx'
import Message from './components/Message.jsx'
import SettingsModal from './components/SettingsModal.jsx'
import { createRouteClient } from './lib/routeClient.js'
import { readSseResponse } from './lib/sse.js'
import { loadRouteCode } from './lib/settings.js'

const ME_QUERY = { me: { resource: 'me', params: { fields: 'id,username,authorities' } } }

const MODES = [
    { value: 'auto', label: 'Auto' },
    { value: 'conversational', label: 'Answer' },
    { value: 'dashboard', label: 'Charts' },
    { value: 'report', label: 'Report' },
    { value: 'presentation', label: 'Slides' },
    { value: 'export', label: 'Data export' },
    { value: 'map', label: 'Map' },
]

const emptyArtefacts = () => ({
    charts: [],
    maps: [],
    reportHtml: '',
    slides: [],
    evidence: [],
    exportData: null,
    dataSource: null,
})

const MyApp = () => {
    const { baseUrl } = useConfig()
    const engine = useDataEngine()
    const { data: meData } = useDataQuery(ME_QUERY)
    const canEditInstance = !!meData?.me?.authorities?.includes('ALL')

    const [routeCode, setRouteCode] = useState(null)
    const [settingsOpen, setSettingsOpen] = useState(false)
    const [connError, setConnError] = useState(null)
    const [notice, setNotice] = useState(null)

    const [conversations, setConversations] = useState([])
    const [activeId, setActiveId] = useState(null)
    const [messages, setMessages] = useState([])
    const [loading, setLoading] = useState(false)
    const [mode, setMode] = useState('auto')
    const [text, setText] = useState('')
    const [suggestions, setSuggestions] = useState([])

    const artefacts = useRef(emptyArtefacts())
    const abortRef = useRef(null)
    const threadRef = useRef(null)

    const client = useMemo(
        () => (routeCode ? createRouteClient(baseUrl, routeCode) : null),
        [baseUrl, routeCode]
    )

    useEffect(() => {
        loadRouteCode(engine).then(({ routeCode }) => setRouteCode(routeCode))
    }, [engine])

    useEffect(() => {
        if (!client) {
            return
        }
        setConnError(null)
        client
            .getJson('api/conversations')
            .then((list) => setConversations(Array.isArray(list) ? list : []))
            .catch((err) => setConnError(err.message))
        client
            .getJson('api/demo/questions')
            .then((qs) => setSuggestions(Array.isArray(qs) ? qs : []))
            .catch(() => setSuggestions([]))
    }, [client])

    const scrollToBottom = useCallback(() => {
        const el = threadRef.current
        if (el) {
            el.scrollTop = el.scrollHeight
        }
    }, [])

    const patchLastAssistant = useCallback((fn) => {
        setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last?.role === 'assistant') {
                next[next.length - 1] = fn(last)
            }
            return next
        })
    }, [])

    const newConversation = useCallback(async () => {
        abortRef.current?.abort()
        const conv = await client.postJson('api/conversations')
        setConversations((prev) => [conv, ...prev])
        setActiveId(conv.id)
        setMessages([])
        return conv.id
    }, [client])

    const selectConversation = useCallback(
        async (id) => {
            if (id === activeId) {
                return
            }
            abortRef.current?.abort()
            setActiveId(id)
            try {
                setMessages(
                    await client.getJson(`api/conversations/${encodeURIComponent(id)}/messages`)
                )
                setTimeout(scrollToBottom, 50)
            } catch (err) {
                setNotice(err.message)
                setMessages([])
            }
        },
        [activeId, client, scrollToBottom]
    )

    const deleteConversation = useCallback(
        async (id) => {
            try {
                await client.postJson(`api/conversations/${encodeURIComponent(id)}/delete`)
                setConversations((prev) => prev.filter((c) => c.id !== id))
                if (id === activeId) {
                    setActiveId(null)
                    setMessages([])
                }
            } catch (err) {
                setNotice(err.message)
            }
        },
        [activeId, client]
    )

    const send = useCallback(
        async (question, modeOverride) => {
            const q = (question || '').trim()
            if (!q || loading || !client) {
                return
            }
            const outputMode = modeOverride ?? mode
            setLoading(true)
            setNotice(null)
            abortRef.current?.abort()
            const controller = new AbortController()
            abortRef.current = controller
            artefacts.current = emptyArtefacts()

            let convId = activeId
            try {
                if (!convId) {
                    convId = await newConversation()
                }
            } catch (err) {
                setNotice(err.message)
                setLoading(false)
                return
            }
            const isFirst = messages.length === 0
            setMessages((prev) => [
                ...prev,
                { role: 'user', content: q },
                { role: 'assistant', content: '', artefacts: null },
            ])
            client
                .postJson(`api/conversations/${convId}/messages`, { role: 'user', content: q })
                .catch(() => {})
            if (isFirst) {
                const title = q.length > 40 ? `${q.slice(0, 40)}…` : q
                client.postJson(`api/conversations/${convId}/rename`, { title }).catch(() => {})
                setConversations((prev) => prev.map((c) => (c.id === convId ? { ...c, title } : c)))
            }

            const pushArtefacts = () =>
                patchLastAssistant((m) => ({ ...m, artefacts: { ...artefacts.current } }))
            try {
                const res = await client.request('api/chat', {
                    method: 'POST',
                    accept: 'text/event-stream',
                    signal: controller.signal,
                    body: {
                        message: q,
                        conversation_id: convId,
                        output_mode: outputMode === 'auto' ? null : outputMode,
                        allow_web: false,
                    },
                })
                await readSseResponse(res, (type, data) => {
                    const a = artefacts.current
                    switch (type) {
                        case 'token':
                            patchLastAssistant((m) => ({
                                ...m,
                                content: (m.content || '') + (data?.text || ''),
                            }))
                            scrollToBottom()
                            break
                        case 'chart_config':
                            a.charts = [...a.charts.filter((c) => c.id !== data.id), data]
                            pushArtefacts()
                            break
                        case 'map_config':
                            a.maps = [...a.maps.filter((m) => m.id !== data.id), data]
                            pushArtefacts()
                            break
                        case 'report_html':
                            a.reportHtml = data?.html || ''
                            pushArtefacts()
                            break
                        case 'slide_manifest':
                            a.slides = Array.isArray(data) ? data : []
                            pushArtefacts()
                            break
                        case 'evidence':
                            a.evidence = Array.isArray(data) ? data : []
                            pushArtefacts()
                            break
                        case 'data_source':
                            a.dataSource = data || null
                            pushArtefacts()
                            break
                        case 'data_ready':
                            a.exportData = data?.data || data
                            pushArtefacts()
                            break
                        case 'clarification':
                            patchLastAssistant((m) => ({
                                ...m,
                                content: data?.question || 'Could you clarify your request?',
                            }))
                            break
                        case 'error':
                            patchLastAssistant((m) => ({
                                ...m,
                                content: data?.user_message || 'An error occurred.',
                            }))
                            break
                        default:
                            break
                    }
                })
            } catch (err) {
                if (err.name !== 'AbortError' && !controller.signal.aborted) {
                    patchLastAssistant((m) => ({ ...m, content: err.message }))
                }
            }

            if (!controller.signal.aborted) {
                setMessages((prev) => {
                    const last = prev[prev.length - 1]
                    const a = artefacts.current
                    const has =
                        a.charts.length ||
                        a.maps.length ||
                        a.reportHtml ||
                        a.slides.length ||
                        a.evidence.length ||
                        a.exportData
                    if (last?.role === 'assistant' && (last.content || has)) {
                        client
                            .postJson(`api/conversations/${convId}/messages`, {
                                role: 'assistant',
                                content: last.content || '',
                                artefacts: a,
                            })
                            .catch(() => {})
                    }
                    return prev
                })
            }
            if (abortRef.current === controller) {
                abortRef.current = null
            }
            setLoading(false)
        },
        [
            activeId,
            client,
            loading,
            messages.length,
            mode,
            newConversation,
            patchLastAssistant,
            scrollToBottom,
        ]
    )

    const submit = () => {
        if (!loading && text.trim()) {
            send(text)
            setText('')
        }
    }

    if (!routeCode) {
        return (
            <CenteredContent>
                <CircularLoader />
            </CenteredContent>
        )
    }

    return (
        <div className={styles.layout}>
            <ConversationList
                conversations={conversations}
                activeId={activeId}
                onSelect={selectConversation}
                onNew={() => newConversation().catch((e) => setNotice(e.message))}
                onDelete={deleteConversation}
            />
            <main className={styles.main}>
                <div className={styles.toolbar}>
                    <h2 className={styles.title}>Ask Analytics</h2>
                    <span className={styles.muted}>Route: {routeCode}</span>
                    <span className={styles.spacer} />
                    <Button
                        small
                        secondary
                        icon={<IconSettings24 />}
                        onClick={() => setSettingsOpen(true)}
                    >
                        Settings
                    </Button>
                </div>

                {connError && (
                    <div className={styles.notice}>
                        <NoticeBox warning title="The assistant backend is not reachable">
                            {connError}{' '}
                            <Button small onClick={() => setSettingsOpen(true)}>
                                Open settings
                            </Button>
                        </NoticeBox>
                    </div>
                )}
                {notice && (
                    <div className={styles.notice}>
                        <NoticeBox error title="Something went wrong">
                            {notice}
                        </NoticeBox>
                    </div>
                )}

                <div className={styles.thread} ref={threadRef} aria-live="polite">
                    {messages.length === 0 && (
                        <div className={styles.welcome}>
                            <h3>Ask a question about your data</h3>
                            <p className={styles.muted}>
                                Trends, comparisons between organisation units, charts, short
                                reports and data exports from this DHIS2 instance&apos;s analytics.
                                Answers are generated by an AI model: check figures against the data
                                before you rely on them.
                            </p>
                            <div className={styles.chips}>
                                {suggestions.map((s) => (
                                    <Chip
                                        key={s.id}
                                        onClick={() => send(s.question, s.output_mode || 'auto')}
                                        disabled={loading}
                                    >
                                        {s.label || s.question}
                                    </Chip>
                                ))}
                            </div>
                        </div>
                    )}
                    {messages.map((m, i) => (
                        <Message
                            key={i}
                            msg={m}
                            client={client}
                            onError={setNotice}
                            loading={loading && i === messages.length - 1 && m.role === 'assistant'}
                        />
                    ))}
                </div>

                <div className={styles.composer}>
                    <div className={styles.modeSelect}>
                        <SingleSelectField
                            dense
                            selected={mode}
                            onChange={({ selected }) => setMode(selected)}
                            label="Output"
                        >
                            {MODES.map((m) => (
                                <SingleSelectOption key={m.value} value={m.value} label={m.label} />
                            ))}
                        </SingleSelectField>
                    </div>
                    <div className={styles.input}>
                        <TextArea
                            value={text}
                            rows={2}
                            placeholder="e.g. Show ANC 1 coverage by district for the last 12 months"
                            onChange={({ value }) => setText(value)}
                            onKeyDown={(_, e) => {
                                if (e?.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault()
                                    submit()
                                }
                            }}
                        />
                    </div>
                    <Button
                        primary
                        onClick={submit}
                        loading={loading}
                        disabled={loading || !text.trim()}
                    >
                        Ask
                    </Button>
                </div>
            </main>
            {settingsOpen && (
                <SettingsModal
                    baseUrl={baseUrl}
                    routeCode={routeCode}
                    canEditInstance={canEditInstance}
                    onClose={() => setSettingsOpen(false)}
                    onSaved={(code) => {
                        setSettingsOpen(false)
                        setActiveId(null)
                        setMessages([])
                        setRouteCode(code)
                    }}
                />
            )}
        </div>
    )
}

export default MyApp
