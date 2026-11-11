import { Tag } from '@dhis2/ui'
import { marked } from 'marked'
import PropTypes from 'prop-types'
import React, { useMemo, useState } from 'react'
import { sanitizeHtml } from '../lib/sanitize.js'
import ChartPanel from './ChartPanel.jsx'
import DataTable from './DataTable.jsx'
import Downloads from './Downloads.jsx'
import MapPanel from './MapPanel.jsx'
import styles from './artefacts.module.css'

const Html = ({ html, className }) => (
    // Sanitised with the browser's own parser (scripts, event handlers and
    // javascript: URLs removed) before it is inserted.
    <div className={className} dangerouslySetInnerHTML={{ __html: sanitizeHtml(html) }} />
)
Html.propTypes = { className: PropTypes.string, html: PropTypes.string }

const Section = ({ title, badge, actions, children }) => (
    <section className={styles.section}>
        <header className={styles.sectionHead}>
            <h3>{title}</h3>
            {badge && <Tag>{badge}</Tag>}
            <span className={styles.spacer} />
            {actions}
        </header>
        {children}
    </section>
)
Section.propTypes = {
    actions: PropTypes.node,
    badge: PropTypes.node,
    children: PropTypes.node,
    title: PropTypes.string,
}

const Message = ({ msg, loading, client, onError }) => {
    const isUser = msg.role === 'user'
    const art = msg.artefacts || {}
    const [sourcesOpen, setSourcesOpen] = useState(false)
    const html = useMemo(() => (msg.content ? marked.parse(msg.content) : ''), [msg.content])

    if (isUser) {
        return (
            <div className={styles.userRow}>
                <div className={styles.userBubble}>{msg.content}</div>
            </div>
        )
    }
    const charts = art.charts || []
    const maps = art.maps || []
    const slides = art.slides || []
    const evidence = art.evidence || []
    const exp = art.exportData
    return (
        <div className={styles.assistantRow}>
            {art.dataSource && art.dataSource.mode && art.dataSource.mode !== 'live' && (
                <Tag neutral>{art.dataSource.label}</Tag>
            )}
            <div className={styles.assistantBubble}>
                {html ? (
                    <Html html={html} className={styles.markdown} />
                ) : loading ? (
                    <span className={styles.typing}>Working on it… answers can take up to a minute.</span>
                ) : null}
            </div>

            {maps.length > 0 && (
                <Section title="Map" badge={maps[0].level_name}>
                    {maps.map((m) => (
                        <MapPanel key={m.id} map={m} />
                    ))}
                </Section>
            )}

            {charts.length > 0 && (
                <Section
                    title="Charts"
                    badge={`${charts.length} chart${charts.length === 1 ? '' : 's'}`}
                >
                    <div className={styles.chartGrid}>
                        {charts.map((c) => (
                            <ChartPanel key={c.id} chart={c} />
                        ))}
                    </div>
                </Section>
            )}

            {art.reportHtml && (
                <Section
                    title="Report"
                    actions={
                        <Downloads
                            client={client}
                            formats={['DOCX', 'PDF']}
                            reportHtml={art.reportHtml}
                            onError={onError}
                        />
                    }
                >
                    <Html html={art.reportHtml} className={styles.report} />
                </Section>
            )}

            {slides.length > 0 && (
                <Section
                    title="Slides"
                    badge={`${slides.length} slides`}
                    actions={
                        <Downloads
                            client={client}
                            formats={['PPTX']}
                            slides={slides}
                            onError={onError}
                        />
                    }
                >
                    <div className={styles.slides}>
                        {slides.map((s, i) => (
                            <div key={i} className={styles.slide}>
                                <h4>{s.title || `Slide ${i + 1}`}</h4>
                                <ul>
                                    {(s.bullets || []).slice(0, 4).map((b, j) => (
                                        <li key={j}>{b}</li>
                                    ))}
                                </ul>
                            </div>
                        ))}
                    </div>
                </Section>
            )}

            {exp && (
                <Section
                    title="Data"
                    badge={`${(exp.rows || []).length} rows`}
                    actions={
                        <Downloads
                            client={client}
                            formats={['XLSX', 'CSV']}
                            exportData={exp}
                            onError={onError}
                        />
                    }
                >
                    <DataTable headers={exp.headers || []} rows={exp.rows || []} maxRows={10} />
                </Section>
            )}

            {evidence.length > 0 && (
                <div className={styles.sources}>
                    <button
                        type="button"
                        className={styles.linkButton}
                        onClick={() => setSourcesOpen((v) => !v)}
                    >
                        {sourcesOpen ? '▾' : '▸'} {evidence.length} source
                        {evidence.length === 1 ? '' : 's'}
                    </button>
                    {sourcesOpen && (
                        <ul className={styles.sourceList}>
                            {evidence.map((e, i) => (
                                <li key={i}>
                                    <Tag neutral>
                                        {e.source === 'dhis2'
                                            ? 'DHIS2'
                                            : e.source === 'tavily'
                                              ? 'Web'
                                              : e.source || 'Source'}
                                    </Tag>{' '}
                                    {e.claim}
                                    {typeof e.confidence === 'number' && (
                                        <span className={styles.muted}>
                                            {' '}
                                            · {(e.confidence * 100).toFixed(0)}%
                                        </span>
                                    )}
                                    {e.source_detail && (
                                        <div className={styles.muted}>{e.source_detail}</div>
                                    )}
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    )
}

Message.propTypes = {
    client: PropTypes.object.isRequired,
    msg: PropTypes.object.isRequired,
    loading: PropTypes.bool,
    onError: PropTypes.func,
}

export default Message
