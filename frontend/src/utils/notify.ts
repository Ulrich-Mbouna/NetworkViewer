import UIkit from 'uikit'

type NotifyStatus = 'primary' | 'success' | 'warning' | 'danger'

/** Sticky toast: stays until the user clicks close. */
export function notify(message: string, status: NotifyStatus = 'primary') {
  UIkit.notification({
    message: `<div class="tp-toast">${message}</div>`,
    status,
    pos: 'top-right',
    timeout: 0,
  })
}

export function notifySuccess(message: string) {
  notify(message, 'success')
}

export function notifyError(message: string) {
  notify(message, 'danger')
}
