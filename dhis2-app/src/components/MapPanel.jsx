/**
 * Choropleth / point map from a map_config event. Uses Plotly's built-in
 * "white-bg" style so no third-party map tiles are requested from the
 * browser: boundaries come from your DHIS2 server via the backend.
 */
import PropTypes from 'prop-types'
import React, { useEffect, useRef } from 'react'
import { loadPlotly } from '../lib/plotly.js'
import DataTable from './DataTable.jsx'
import styles from './artefacts.module.css'

const HEIGHT = 480

function fitView(bbox, width, height) {
    if (!Array.isArray(bbox) || bbox.length !== 4) {
        return { center: { lon: 0, lat: 0 }, zoom: 1 }
    }
    const [minLon, minLat, maxLon, maxLat] = bbox
    const latRad = (lat) => {
        const s = Math.sin((lat * Math.PI) / 180)
        return Math.log((1 + s) / (1 - s)) / 2
    }
    const zLon = Math.log2((width * 360) / (512 * Math.max(maxLon - minLon, 0.01)))
    const zLat = Math.log2(
        (height * 2 * Math.PI) / (512 * Math.max(latRad(maxLat) - latRad(minLat), 0.0002))
    )
    return {
        center: { lon: (minLon + maxLon) / 2, lat: (minLat + maxLat) / 2 },
        zoom: Math.max(0, Math.min(zLon, zLat, 14) - 0.15),
    }
}

function buildTraces(map) {
    const fc = map.geojson || { type: 'FeatureCollection', features: [] }
    const feats = fc.features || []
    const pts = map.points || []
    const hover = '<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>'
    const groups = (map.legend || []).map((c, i) => ({ ...c, i }))
    groups.push({ i: -1, label: 'No data', color: map.no_data_color || '#d1d5db' })
    const traces = []
    for (const g of groups) {
        const inClass = feats.filter((f) => (f.properties?.class ?? -1) === g.i)
        const ptsIn = pts.filter((p) => (p.class ?? -1) === g.i)
        if (inClass.length) {
            traces.push({
                type: 'choroplethmap',
                geojson: fc,
                featureidkey: 'properties.id',
                locations: inClass.map((f) => f.properties.id),
                z: inClass.map(() => 1),
                customdata: inClass.map((f) => [f.properties.name, f.properties.label]),
                hovertemplate: hover,
                colorscale: [
                    [0, g.color],
                    [1, g.color],
                ],
                showscale: false,
                marker: { line: { color: '#ffffff', width: 1 }, opacity: 0.9 },
                name: g.label,
                legendgroup: String(g.i),
                showlegend: true,
            })
        }
        if (ptsIn.length) {
            traces.push({
                type: 'scattermap',
                mode: 'markers',
                lon: ptsIn.map((p) => p.lon),
                lat: ptsIn.map((p) => p.lat),
                customdata: ptsIn.map((p) => [p.name, p.label]),
                hovertemplate: hover,
                marker: { size: 11, color: g.color },
                name: g.label,
                legendgroup: String(g.i),
                showlegend: !inClass.length,
            })
        }
    }
    return traces
}

const MapPanel = ({ map }) => {
    const ref = useRef(null)
    useEffect(() => {
        const el = ref.current
        if (!el) {
            return undefined
        }
        const { center, zoom } = fitView(map.bbox, el.clientWidth || 800, HEIGHT - 60)
        let cancelled = false
        loadPlotly().then((Plotly) => {
            if (cancelled || !el.isConnected) {
                return
            }
            Plotly.react(
                el,
                buildTraces(map),
                {
                    title: {
                        text: map.title || 'Map',
                        x: 0.01,
                        xanchor: 'left',
                        font: { size: 16 },
                    },
                    height: HEIGHT,
                    margin: { l: 0, r: 0, t: 48, b: 0 },
                    map: { style: 'white-bg', center, zoom },
                    legend: {
                        x: 0.01,
                        y: 0.02,
                        yanchor: 'bottom',
                        bgcolor: 'rgba(255,255,255,0.9)',
                    },
                },
                { responsive: true, displaylogo: false, scrollZoom: true }
            )
        })
        return () => {
            cancelled = true
            loadPlotly().then((Plotly) => Plotly.purge(el))
        }
    }, [map])
    const headers = map.table?.headers || ['Organisation unit', 'Value']
    return (
        <div>
            <div className={styles.map} ref={ref} />
            <DataTable headers={headers} rows={map.table?.rows || []} maxRows={50} />
        </div>
    )
}

MapPanel.propTypes = { map: PropTypes.object.isRequired }

export default MapPanel
