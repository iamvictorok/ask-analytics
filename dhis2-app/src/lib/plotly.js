// Plotly is large; load it only when the first chart or map is shown.
let promise = null
export const loadPlotly = () => {
    if (!promise) {
        promise = import('plotly.js-dist-min').then((m) => m.default || m)
    }
    return promise
}
