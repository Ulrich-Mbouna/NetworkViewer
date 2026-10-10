import UIkit from 'uikit'

type NotifyStatus = 'primary' | 'success' | 'warning' | 'danger'

const TIMEOUTS: Record<NotifyStatus, number> = {
  primary: 3500,
  success: 3500,
  warning: 5000,
  danger: 6000,
}

/** Toast auto-dismiss (fermeture manuelle toujours possible). */
export function notify(message: string, status: NotifyStatus = 'primary') {
  UIkit.notification({
    message: `<div class="tp-toast">${message}</div>`,
    status,
    pos: 'top-right',
    timeout: TIMEOUTS[status],
  })
}

export function notifySuccess(message: string) {
  notify(message, 'success')
}

export function notifyError(message: string) {
  notify(message, 'danger')
}
