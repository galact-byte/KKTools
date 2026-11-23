import React from 'react'
import { AlertTriangle, X } from 'lucide-react'

export interface ConfirmDialogState {
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
  onConfirm: () => void
}

interface ConfirmModalProps {
  dialog: ConfirmDialogState | null
  onClose: () => void
}

/** 实心不透明确认弹窗（壁纸模式下也保持清晰可读）。 */
export const ConfirmModal: React.FC<ConfirmModalProps> = ({ dialog, onClose }) => {
  if (!dialog) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(10, 18, 32, 0.48)' }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <div className="kk-popover w-full max-w-md p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
              style={{
                backgroundColor: dialog.danger ? 'var(--danger-soft)' : 'var(--warning-soft)',
                color: dialog.danger ? 'var(--danger)' : 'var(--warning)',
              }}
            >
              <AlertTriangle size={16} />
            </span>
            <h3
              id="confirm-dialog-title"
              className="text-[15px] font-bold"
              style={{ color: 'var(--text-strong)' }}
            >
              {dialog.title}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="kk-btn-ghost flex h-7 w-7 items-center justify-center rounded-[var(--radius-sm)] cursor-pointer"
            aria-label="关闭"
          >
            <X size={14} />
          </button>
        </div>

        <p
          className="mt-3 whitespace-pre-line text-[13px] leading-relaxed"
          style={{ color: 'var(--text)' }}
        >
          {dialog.message}
        </p>

        <div className="mt-5 flex items-center justify-end gap-2">
          <button type="button" onClick={onClose} className="kk-btn">
            {dialog.cancelLabel || '取消'}
          </button>
          <button
            type="button"
            onClick={() => {
              const fn = dialog.onConfirm
              onClose()
              fn()
            }}
            className={dialog.danger ? 'kk-btn kk-btn-danger' : 'kk-btn kk-btn-primary'}
          >
            {dialog.confirmLabel || '确认继续'}
          </button>
        </div>
      </div>
    </div>
  )
}
