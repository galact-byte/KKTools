import React, { useEffect } from 'react'
import { Maximize2, Sparkles, X } from 'lucide-react'
import { EditorPage } from '../pages/EditorPage'
import type { CardDetail, CardModCheckResult, LogEntry } from '../types/kk'

interface CardEditorModalProps {
  card: CardDetail | null
  coverPreviewUrl: string
  dirty: boolean
  saving: boolean
  modCheck: CardModCheckResult | null
  checkingMods: boolean
  onRequestClose: () => void
  onExpandToPage: () => void
  onPickCover: () => void
  onUpdateParam: (updater: (param: CardDetail['parameter']) => CardDetail['parameter']) => void
  onSaveAs: () => void
  onSaveOverwrite: () => void
  onReset: () => void
  onCopyModIds: () => void
  onCheckCardMods: () => void
  onNotify?: (msg: string, tone?: 'info' | 'ok' | 'warn' | 'error') => void
  onLog?: (level: LogEntry['level'], source: string, msg: string) => void
}

/** 画廊原地大浮层编辑工作台：不打断画廊筛选与滚动位置，支持 Esc 退出与未保存保护。 */
export const CardEditorModal: React.FC<CardEditorModalProps> = ({
  card,
  coverPreviewUrl,
  dirty,
  saving,
  modCheck,
  checkingMods,
  onRequestClose,
  onExpandToPage,
  onPickCover,
  onUpdateParam,
  onSaveAs,
  onSaveOverwrite,
  onReset,
  onCopyModIds,
  onCheckCardMods,
  onNotify,
  onLog,
}) => {
  useEffect(() => {
    if (!card) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onRequestClose()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [card, onRequestClose])

  if (!card) return null

  const fullName =
    [card.parameter.lastname, card.parameter.firstname].filter(Boolean).join(' ') || card.fileName

  return (
    <div
      className="kk-backdrop-enter fixed inset-0 z-40 flex items-center justify-center p-5"
      style={{ backgroundColor: 'rgba(10, 18, 34, 0.46)', backdropFilter: 'blur(4px)' }}
      role="dialog"
      aria-modal="true"
      aria-label={`编辑角色卡：${fullName}`}
      onClick={(e) => {
        if (e.target === e.currentTarget) onRequestClose()
      }}
    >
      <div
        className="kk-modal-enter flex h-[min(780px,88vh)] w-[min(1080px,92vw)] flex-col overflow-hidden rounded-[var(--radius-xl)]"
        style={{
          backgroundColor: 'var(--bg)',
          border: '1px solid var(--border-strong)',
          boxShadow: 'var(--shadow-float)',
        }}
      >
        {/* 浮层顶栏 */}
        <div
          className="flex h-12 shrink-0 items-center justify-between px-4"
          style={{
            backgroundColor: 'var(--surface)',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <div className="flex min-w-0 items-center gap-2.5">
            <span
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[7px]"
              style={{ backgroundColor: 'var(--primary-soft)', color: 'var(--primary)' }}
            >
              <Sparkles size={13} />
            </span>
            <span className="truncate text-[14px] font-bold" style={{ color: 'var(--text-strong)' }}>
              {fullName}
            </span>
            <span
              className="font-mono-num hidden truncate text-[11.5px] sm:inline"
              style={{ color: 'var(--text-dim)' }}
            >
              {card.fileName}
            </span>
            {dirty && (
              <span
                className="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold"
                style={{ backgroundColor: 'var(--warning-soft)', color: 'var(--warning)' }}
              >
                未保存
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={onExpandToPage}
              className="kk-btn-ghost inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-sm)] px-2.5 text-[12px] cursor-pointer"
              title="转到完整「角色编辑」页面继续编辑"
            >
              <Maximize2 size={13} />
              <span>独立页打开</span>
            </button>
            <button
              type="button"
              onClick={onRequestClose}
              className="kk-btn h-8 px-2.5 text-[12px]"
              aria-label="关闭编辑弹窗"
            >
              <X size={14} />
              <span>关闭</span>
            </button>
          </div>
        </div>

        {/* 复用完整角色编辑台 */}
        <div className="min-h-0 flex-1 overflow-hidden">
          <EditorPage
            card={card}
            coverPreviewUrl={coverPreviewUrl}
            dirty={dirty}
            saving={saving}
            modCheck={modCheck}
            checkingMods={checkingMods}
            inModal
            onPickCardFile={() => {}}
            onPickCover={onPickCover}
            onUpdateParam={onUpdateParam}
            onSaveAs={onSaveAs}
            onSaveOverwrite={onSaveOverwrite}
            onReset={onReset}
            onCopyModIds={onCopyModIds}
            onCheckCardMods={onCheckCardMods}
            onNotify={onNotify}
            onLog={onLog}
          />
        </div>
      </div>
    </div>
  )
}
