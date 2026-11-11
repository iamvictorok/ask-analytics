import PropTypes from 'prop-types'
import React, { useEffect, useRef } from 'react'
import { loadPlotly } from '../lib/plotly.js'
import styles from './artefacts.module.css'

const PALETTE = [
    '#147cd7',
    '#0f6e6e',
    '#f2a541',
    '#d64545',
    '#7a5af8',
    '#2e9e5b',
    '#e07b39',
    '#5b6b7f',
]

function buildTraces(chart) {
    const type = chart.type || 'bar'
    return (chart.series || []).map((s, i) => {
        if (type === 'pie') {
            return {
                type: 'pie',
                labels: s.labels || [],
                values: s.values || [],
                hole: 0.35,
                marker: { colors: PALETTE },
            }
        }
        if (type === 'table') {
            return {
                type: 'table',
                header: {
                    values: s.header || [],
                    fill: { color: '#e8edf2' },
                    align: 'left',
                    font: { size: 12, color: '#212934' },
                },
                cells: {
                    values: s.cells || [],
                    align: 'left',
                    font: { size: 11, color: '#404b5a' },
                },
            }
        }
        const color = PALETTE[i % PALETTE.length]
        return {
            type: type === 'line' ? 'scatter' : type,
            mode: type === 'line' ? 'lines+markers' : s.mode || undefined,
            x: s.x || [],
            y: s.y || [],
            name: s.name || '',
            marker: { color },
            line: type === 'line' ? { color, width: 2.5 } : undefined,
        }
    })
}

// The backend ships a dark theme for its own UI; restyle for the DHIS2 UI.
const axis = (a) =>
    a
        ? {
              ...a,
              gridcolor: '#e8edf2',
              zerolinecolor: '#c4cdd7',
              linecolor: '#c4cdd7',
              color: '#404b5a',
          }
        : a
function lightLayout(src) {
    const title = typeof src.title === 'string' ? { text: src.title } : src.title || {}
    return {
        ...src,
        title: { ...title, font: { size: 15, color: '#212934' } },
        xaxis: axis(src.xaxis) || { gridcolor: '#e8edf2', color: '#404b5a' },
        yaxis: axis(src.yaxis) || { gridcolor: '#e8edf2', color: '#404b5a' },
        colorway: PALETTE,
        autosize: true,
        height: 340,
        paper_bgcolor: '#ffffff',
        plot_bgcolor: '#ffffff',
        font: { color: '#404b5a', family: 'Roboto, sans-serif' },
        margin: { l: 56, r: 16, t: 48, b: 72 },
    }
}

const ChartPanel = ({ chart }) => {
    const ref = useRef(null)
    useEffect(() => {
        const el = ref.current
        if (!el) {
            return undefined
        }
        const layout = lightLayout(chart.layout || {})
        let cancelled = false
        loadPlotly().then((Plotly) => {
            if (cancelled || !el.isConnected) {
                return
            }
            Plotly.react(el, buildTraces(chart), layout, {
                responsive: true,
                displaylogo: false,
                modeBarButtonsToRemove: ['lasso2d', 'select2d'],
            })
        })
        return () => {
            cancelled = true
            loadPlotly().then((Plotly) => Plotly.purge(el))
        }
    }, [chart])
    return <div className={styles.chart} ref={ref} />
}

ChartPanel.propTypes = { chart: PropTypes.object.isRequired }

export default ChartPanel
