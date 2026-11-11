import { Button, Menu, MenuItem, IconAdd16, IconDelete16 } from '@dhis2/ui'
import PropTypes from 'prop-types'
import React from 'react'
import styles from '../App.module.css'

const ConversationList = ({ conversations, activeId, onSelect, onNew, onDelete }) => (
    <aside className={styles.sidebar}>
        <div className={styles.sidebarHead}>
            <Button small icon={<IconAdd16 />} onClick={onNew}>
                New conversation
            </Button>
        </div>
        <Menu dense>
            {conversations.map((c) => (
                <MenuItem
                    key={c.id}
                    active={c.id === activeId}
                    label={c.title || 'Untitled'}
                    onClick={() => onSelect(c.id)}
                    suffix={
                        <span
                            role="button"
                            tabIndex={0}
                            title="Delete conversation"
                            className={styles.deleteIcon}
                            onClick={(e) => {
                                e.stopPropagation()
                                onDelete(c.id)
                            }}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                    e.stopPropagation()
                                    onDelete(c.id)
                                }
                            }}
                        >
                            <IconDelete16 />
                        </span>
                    }
                />
            ))}
        </Menu>
        {conversations.length === 0 && <p className={styles.muted}>No conversations yet.</p>}
    </aside>
)

ConversationList.propTypes = {
    conversations: PropTypes.array.isRequired,
    onDelete: PropTypes.func.isRequired,
    onNew: PropTypes.func.isRequired,
    onSelect: PropTypes.func.isRequired,
    activeId: PropTypes.string,
}

export default ConversationList
