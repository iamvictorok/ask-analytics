import { Button, ButtonStrip } from '@dhis2/ui'
import PropTypes from 'prop-types'
import React, { useState } from 'react'

const FORMATS = {
    DOCX: { path: 'api/generate/docx', kind: 'report' },
    PDF: { path: 'api/generate/pdf', kind: 'report' },
    PPTX: { path: 'api/generate/pptx', kind: 'slides' },
    XLSX: { path: 'api/export/xlsx', kind: 'export' },
    CSV: { path: 'api/export/csv', kind: 'export' },
}

const Downloads = ({ client, formats, reportHtml, slides, exportData, onError }) => {
    const [busy, setBusy] = useState('')
    const download = async (label) => {
        const fmt = FORMATS[label]
        setBusy(label)
        try {
            const body =
                fmt.kind === 'report'
                    ? { html: reportHtml || '<p>No report content</p>', title: 'Analytics report' }
                    : fmt.kind === 'slides'
                      ? { slides: slides || [], title: 'Analytics briefing' }
                      : exportData || { rows: [], headers: [] }
            const meta = await client.postJson(fmt.path, body)
            if (!meta.file_id) {
                throw new Error('No file was produced.')
            }
            const res = await client.request(`api/download/${encodeURIComponent(meta.file_id)}`, {
                accept: '*/*',
            })
            const url = URL.createObjectURL(await res.blob())
            const a = document.createElement('a')
            a.href = url
            a.download = meta.filename || `${meta.file_id}.${label.toLowerCase()}`
            document.body.appendChild(a)
            a.click()
            a.remove()
            URL.revokeObjectURL(url)
        } catch (err) {
            onError?.(`Download failed: ${err.message}`)
        } finally {
            setBusy('')
        }
    }
    return (
        <ButtonStrip>
            {formats.map((f) => (
                <Button
                    key={f}
                    small
                    secondary
                    loading={busy === f}
                    disabled={!!busy}
                    onClick={() => download(f)}
                >
                    {f}
                </Button>
            ))}
        </ButtonStrip>
    )
}

Downloads.propTypes = {
    client: PropTypes.object.isRequired,
    formats: PropTypes.arrayOf(PropTypes.string).isRequired,
    exportData: PropTypes.object,
    reportHtml: PropTypes.string,
    slides: PropTypes.array,
    onError: PropTypes.func,
}

export default Downloads
