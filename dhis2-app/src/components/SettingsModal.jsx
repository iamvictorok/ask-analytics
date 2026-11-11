import { useDataEngine } from '@dhis2/app-runtime'
import {
    Button,
    ButtonStrip,
    InputField,
    Modal,
    ModalActions,
    ModalContent,
    ModalTitle,
    NoticeBox,
} from '@dhis2/ui'
import PropTypes from 'prop-types'
import React, { useState } from 'react'
import { createRouteClient, isValidRouteCode } from '../lib/routeClient.js'
import { saveInstanceRouteCode, saveUserRouteCode } from '../lib/settings.js'

const SettingsModal = ({ baseUrl, routeCode, canEditInstance, onClose, onSaved }) => {
    const engine = useDataEngine()
    const [code, setCode] = useState(routeCode)
    const [status, setStatus] = useState(null)
    const [busy, setBusy] = useState(false)
    const valid = isValidRouteCode(code)

    const test = async () => {
        setBusy(true)
        setStatus(null)
        try {
            const health = await createRouteClient(baseUrl, code).getJson('health')
            setStatus({
                ok: true,
                text: `Connected. Backend mode: ${health.deployment_mode}, model provider: ${health.llm_provider}.`,
            })
        } catch (err) {
            setStatus({ ok: false, text: err.message })
        } finally {
            setBusy(false)
        }
    }
    const save = async (scope) => {
        setBusy(true)
        try {
            if (scope === 'instance') {
                await saveInstanceRouteCode(engine, code)
            } else {
                await saveUserRouteCode(engine, code)
            }
            onSaved(code)
        } catch (err) {
            setStatus({ ok: false, text: `Could not save: ${err.message}` })
            setBusy(false)
        }
    }
    return (
        <Modal onClose={onClose} position="middle">
            <ModalTitle>Assistant connection</ModalTitle>
            <ModalContent>
                <p>
                    This app reaches its backend only through a DHIS2 Route. Enter the code of the
                    Route your administrator created in Route Manager. No URLs or keys are stored in
                    the app.
                </p>
                <InputField
                    label="Route code"
                    value={code}
                    onChange={({ value }) => setCode(value.trim())}
                    validationText={valid ? '' : 'Letters, numbers, - and _ only'}
                    error={!valid}
                />
                {status && (
                    <div style={{ marginTop: 12 }}>
                        <NoticeBox
                            error={!status.ok}
                            title={status.ok ? 'Route works' : 'Route check failed'}
                        >
                            {status.text}
                        </NoticeBox>
                    </div>
                )}
            </ModalContent>
            <ModalActions>
                <ButtonStrip end>
                    <Button onClick={onClose} secondary>
                        Cancel
                    </Button>
                    <Button onClick={test} disabled={!valid || busy}>
                        Test connection
                    </Button>
                    {canEditInstance && (
                        <Button onClick={() => save('instance')} disabled={!valid || busy}>
                            Save for everyone
                        </Button>
                    )}
                    <Button primary onClick={() => save('user')} disabled={!valid || busy}>
                        Save for me
                    </Button>
                </ButtonStrip>
            </ModalActions>
        </Modal>
    )
}

SettingsModal.propTypes = {
    baseUrl: PropTypes.string.isRequired,
    canEditInstance: PropTypes.bool.isRequired,
    routeCode: PropTypes.string.isRequired,
    onClose: PropTypes.func.isRequired,
    onSaved: PropTypes.func.isRequired,
}

export default SettingsModal
