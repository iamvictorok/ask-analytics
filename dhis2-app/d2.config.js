/** @type {import('@dhis2/cli-app-scripts').D2Config} */
const config = {
    type: 'app',
    name: 'ask-analytics',
    title: 'Ask Analytics',
    description:
        'Ask questions about aggregate DHIS2 data in plain language and get answers with charts, tables and reports. Answers come from a self-hosted backend reached only through a DHIS2 Route.',
    author: 'Victor Kola Omolaiye',
    minDHIS2Version: '2.40',
    // Reserved DataStore namespace: only users with access to this app can
    // read/write it. Holds non-secret settings only (the Route code).
    dataStoreNamespace: 'ask-analytics',
    // Optional: give this authority to user roles and list it on the Route
    // ("authorities") so non-superusers can run the Route from this app.
    customAuthorities: ['ASK_ANALYTICS_RUN_ROUTE'],
    entryPoints: {
        app: './src/App.jsx',
    },
}

module.exports = config
