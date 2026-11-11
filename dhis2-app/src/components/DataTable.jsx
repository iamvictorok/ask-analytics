import {
    DataTable as UiTable,
    DataTableBody,
    DataTableCell,
    DataTableColumnHeader,
    DataTableHead,
    DataTableRow,
} from '@dhis2/ui'
import PropTypes from 'prop-types'
import React from 'react'
import styles from './artefacts.module.css'

const DataTable = ({ headers, rows, maxRows }) => {
    const shown = maxRows ? rows.slice(0, maxRows) : rows
    return (
        <div className={styles.tableWrap}>
            <UiTable scrollHeight="320px" layout="auto">
                <DataTableHead>
                    <DataTableRow>
                        {headers.map((h, i) => (
                            <DataTableColumnHeader key={i} fixed top="0">
                                {h}
                            </DataTableColumnHeader>
                        ))}
                    </DataTableRow>
                </DataTableHead>
                <DataTableBody>
                    {shown.map((r, i) => (
                        <DataTableRow key={i}>
                            {r.map((c, j) => (
                                <DataTableCell key={j}>
                                    {c === null || c === undefined ? '—' : String(c)}
                                </DataTableCell>
                            ))}
                        </DataTableRow>
                    ))}
                </DataTableBody>
            </UiTable>
            {maxRows && rows.length > maxRows && (
                <p className={styles.muted}>
                    Showing {maxRows} of {rows.length} rows. Download for the full table.
                </p>
            )}
        </div>
    )
}

DataTable.propTypes = {
    headers: PropTypes.array.isRequired,
    rows: PropTypes.array.isRequired,
    maxRows: PropTypes.number,
}

export default DataTable
