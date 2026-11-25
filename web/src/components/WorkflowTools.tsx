import React, { useEffect, useState } from 'react'
import {
  AlertTriangle,
  ArrowLeftRight,
  CheckCircle2,
  Download,
  ExternalLink,
  Eye,
  FolderInput,
  FolderOpen,
  Save,
  ShieldCheck,
  Tag,
  UserRound,
  Wrench,
} from 'lucide-react'
import { backend, waitTask, type ImportPlan } from '../lib/bridge'
import {
  getCardConvertCapability,
  normalizeDisplayAuthor,
  normalizeUserId,
} from '../lib/cardDisplay'
import type { AuthorSource, CardType, LogEntry } from '../types/kk'
import { ConfirmModal, type ConfirmDialogState } from './ConfirmModal'

type NotifyFn = (msg: string, tone?: 'info' | 'ok' | 'warn' | 'error') => void
type LogFn = (level: LogEntry['level'], source: string, msg: string) => void

export const DataExportButton: React.FC<{
  kind: 'list' | 'character' | 'scene'
  paths: string[]
  format: 'csv' | 'json' | 'txt'
  disabled?: boolean
  label: string
  className?: string
  title?: string
  onExported?: (outPath: string) => void
  onNotify?: NotifyFn
  onLog?: LogFn
}> = ({ kind, paths, format, disabled, label, className, title, onExported, onNotify, onLog }) => {
  const [busy, setBusy] = useState(false)

  const run = async () => {
    setBusy(true)
    try {
      const pick = await backend.pickDirectory('选择资料导出目录')
      if (!pick.ok) {
        const msg = pick.error || '无法选择目录'
        onNotify?.(msg, 'error')
        onLog?.('error', 'EXPORT', msg)
        return
      }
      if (!pick.data) return
      const start = await backend.startExportData({ kind, paths, outDir: pick.data, format })
      if (!start.ok || !start.data) {
        const msg = start.error || '无法启动导出任务'
        onNotify?.(msg, 'error')
        onLog?.('error', 'EXPORT', msg)
        return
      }
      const done = await waitTask<{ path: string }>(start.data.taskId)
      if (done.ok && done.data) {
        onExported?.(done.data.path)
        onNotify?.(`资料已导出：${done.data.path}`, 'ok')
        onLog?.('ok', 'EXPORT', `资料已导出 (${kind}/${format}) -> ${done.data.path}`)
      } else {
        const msg = done.error || '导出失败'
        onNotify?.(msg, 'error')
        onLog?.('error', 'EXPORT', msg)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <button
      type="button"
      title={title}
      className={className || 'kk-btn text-[12px]'}
      disabled={busy || disabled || paths.length === 0}
      onClick={() => void run()}
    >
      <Download size={13} />
      <span>{busy ? '导出中…' : label}</span>
    </button>
  )
}

export const CardTagEditor: React.FC<{
  path: string
  onSaved: (tags: string[]) => void
  onNotify?: NotifyFn
  onLog?: LogFn
}> = ({ path, onSaved, onNotify, onLog }) => {
  const [text, setText] = useState('')
  const [savedTags, setSavedTags] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [errorText, setErrorText] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setText('')
    setSavedTags([])
    setErrorText('')
    void backend.getCardTags(path).then((r) => {
      if (!active) return
      if (r.ok && r.data) {
        setSavedTags(r.data)
        setText(r.data.join('，'))
      } else {
        setErrorText(r.error || '标签读取失败')
      }
      setLoading(false)
    })
    return () => {
      active = false
    }
  }, [path])

  const savedJoined = savedTags.join('，')
  const dirty = text !== savedJoined

  const save = async () => {
    if (loading || busy || !dirty) return
    setBusy(true)
    setErrorText('')
    const parsed = text
      .split(/[,，\n]/)
      .map((t) => t.trim())
      .filter(Boolean)
    const r = await backend.setCardTags(path, parsed)
    setBusy(false)
    if (r.ok && r.data) {
      setSavedTags(r.data)
      setText(r.data.join('，'))
      onSaved(r.data)
      onNotify?.(r.data.length > 0 ? `已保存 ${r.data.length} 个标签` : '已清空自定义标签', 'ok')
      onLog?.('ok', 'TAGS', `已更新标签 (${r.data.length}) -> ${path}`)
    } else {
      const msg = r.error || '标签保存失败'
      setErrorText(msg)
      onNotify?.(msg, 'error')
      onLog?.('error', 'TAGS', msg)
    }
  }

  return (
    <div className="kk-surface-alt flex flex-col gap-2 p-3 text-[12px]">
      <div className="flex items-center justify-between gap-2">
        <label
          className="flex items-center gap-1.5 font-medium"
          style={{ color: 'var(--text-strong)' }}
          htmlFor="card-tags"
        >
          <Tag size={12} style={{ color: 'var(--primary)' }} />
          <span>自定义标签</span>
        </label>
        <span className="text-[11px]" style={{ color: dirty ? 'var(--warning)' : 'var(--text-dim)' }}>
          {dirty ? '未保存' : '仅存本机'}
        </span>
      </div>

      {savedTags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {savedTags.map((tag) => (
            <span
              key={tag}
              className="rounded-full px-2 py-0.5 text-[11px] font-medium"
              style={{
                backgroundColor: 'var(--primary-soft)',
                color: 'var(--primary)',
              }}
            >
              #{tag}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center gap-1.5">
        <input
          id="card-tags"
          className="kk-input h-8 min-w-0 flex-1 py-1 text-[12px]"
          placeholder="逗号分隔，如：收藏，待补 Mod"
          value={text}
          disabled={loading || busy}
          maxLength={2048}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              void save()
            }
          }}
        />
        <button
          type="button"
          className="kk-btn h-8 shrink-0 px-2.5 text-[12px]"
          disabled={loading || busy || !dirty}
          onClick={() => void save()}
        >
          <Save size={12} />
          <span>{busy ? '保存中' : '保存'}</span>
        </button>
      </div>

      {errorText && (
        <span role="status" className="text-[11px]" style={{ color: 'var(--danger)' }}>
          {errorText}
        </span>
      )}
    </div>
  )
}

export const AUTHOR_SOURCE_LABEL: Record<AuthorSource, string> = {
  card: '卡内记录',
  manual: '手动设置',
  userid: 'KKS 创作者 ID',
  '': '',
}

export const CardAuthorEditor: React.FC<{
  path: string
  initialAuthor?: string
  initialSource?: AuthorSource
  initialHistory?: string[]
  userId?: string
  onSaved: (author: string, source: AuthorSource, history: string[]) => void
  onNotify?: NotifyFn
  onLog?: LogFn
}> = ({
  path,
  initialAuthor = '',
  initialSource = '',
  initialHistory = [],
  userId = '',
  onSaved,
  onNotify,
  onLog,
}) => {
  const cleanInitialAuthor = normalizeDisplayAuthor(initialAuthor)
  const [text, setText] = useState(cleanInitialAuthor)
  const [savedManual, setSavedManual] = useState(initialSource === 'manual' ? cleanInitialAuthor : '')
  const [cardAuthor, setCardAuthor] = useState(initialSource === 'manual' ? '' : cleanInitialAuthor)
  const [source, setSource] = useState<AuthorSource>(cleanInitialAuthor ? initialSource : '')
  const [history, setHistory] = useState<string[]>(initialHistory)
  const [uid, setUid] = useState(normalizeUserId(userId))
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    void backend.getCardAuthor(path).then((r) => {
      if (!active) return
      if (r.ok && r.data) {
        const nextManual = normalizeDisplayAuthor(r.data.manualAuthor)
        const nextCard = normalizeDisplayAuthor(r.data.cardAuthor)
        const nextEffective = nextManual || nextCard
        setText(nextEffective)
        setSavedManual(nextManual)
        setCardAuthor(nextCard)
        setSource(nextEffective ? r.data.authorSource || '' : '')
        setHistory(r.data.authorHistory || [])
        setUid(normalizeUserId(r.data.userId))
      }
      setLoading(false)
    })
    return () => {
      active = false
    }
  }, [path])

  const effectiveBaseline = savedManual || cardAuthor
  const dirty = text.trim() !== effectiveBaseline

  const save = async (nextVal?: string) => {
    if (loading || busy) return
    const val = (nextVal ?? text).trim()
    setBusy(true)
    const r = await backend.setCardAuthor(path, val)
    setBusy(false)
    if (r.ok && r.data) {
      const nextManual = normalizeDisplayAuthor(r.data.manualAuthor)
      const nextCard = normalizeDisplayAuthor(r.data.cardAuthor)
      const nextEffective = normalizeDisplayAuthor(r.data.author)
      setSavedManual(nextManual)
      setCardAuthor(nextCard)
      setSource(nextEffective ? r.data.authorSource || '' : '')
      setHistory(r.data.authorHistory || [])
      setText(nextEffective)
      setUid(normalizeUserId(r.data.userId))
      onSaved(nextEffective, nextEffective ? r.data.authorSource || '' : '', r.data.authorHistory || [])
      onNotify?.(
        val ? `已设置作者：${nextEffective}` : '已清除手动作者，恢复卡内识别',
        'ok',
      )
      onLog?.('ok', 'AUTHOR', `${val ? `设置作者=${val}` : '清除手动作者'} -> ${path}`)
    } else {
      const msg = r.error || '作者保存失败'
      onNotify?.(msg, 'error')
      onLog?.('error', 'AUTHOR', msg)
    }
  }

  return (
    <div className="kk-surface-alt flex flex-col gap-2 p-3 text-[12px]">
      <div className="flex items-center justify-between gap-2">
        <label
          className="flex items-center gap-1.5 font-medium"
          style={{ color: 'var(--text-strong)' }}
          htmlFor="card-author-input"
        >
          <UserRound size={12} style={{ color: 'var(--primary)' }} />
          <span>卡片作者</span>
        </label>
        <span
          className="rounded-full px-1.5 py-[1px] text-[10.5px]"
          style={{
            backgroundColor: source === 'card' ? 'var(--success-soft)' : 'var(--surface)',
            color: source === 'card' ? 'var(--success)' : 'var(--text-dim)',
          }}
        >
          {AUTHOR_SOURCE_LABEL[source] || '未记录'}
        </span>
      </div>

      <div className="flex items-center gap-1.5">
        <input
          id="card-author-input"
          className="kk-input h-8 min-w-0 flex-1 py-1 text-[12px]"
          placeholder="留空则使用卡内记录，或输入自定义作者"
          value={text}
          disabled={loading || busy}
          maxLength={80}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              if (dirty) void save()
            }
          }}
        />
        <button
          type="button"
          className="kk-btn h-8 shrink-0 px-2.5 text-[12px]"
          disabled={loading || busy || !dirty}
          onClick={() => void save()}
        >
          <Save size={12} />
          <span>{busy ? '保存中' : '保存'}</span>
        </button>
      </div>

      {savedManual && cardAuthor && (
        <div className="flex items-center justify-between text-[11px]" style={{ color: 'var(--text-dim)' }}>
          <span className="truncate">卡内原记录：{cardAuthor}</span>
          <button
            type="button"
            disabled={busy}
            onClick={() => void save('')}
            className="shrink-0 underline cursor-pointer"
            style={{ color: 'var(--primary)' }}
          >
            恢复
          </button>
        </div>
      )}

      {history.length > 1 && (
        <div className="text-[11px]" style={{ color: 'var(--text-dim)' }}>
          修改链：{history.join(' → ')}
        </div>
      )}

      {uid && (
        <div className="font-mono-num truncate text-[10.5px]" style={{ color: 'var(--text-dim)' }} title={uid}>
          KKS userID: {uid}
        </div>
      )}
    </div>
  )
}

export const ConvertCardButton: React.FC<{
  path: string
  game: string
  cardType?: CardType
  disabled?: boolean
  className?: string
  title?: string
  onConverted?: (savedPath: string, targetGame: 'KK' | 'KKS') => void
  onNotify?: NotifyFn
  onLog?: LogFn
}> = ({
  path,
  game,
  cardType = 'character',
  disabled,
  className,
  title,
  onConverted,
  onNotify,
  onLog,
}) => {
  const [busy, setBusy] = useState(false)
  const cap = getCardConvertCapability(cardType, game)
  const target = cap.targetGame
  const label = !cap.canConvert
    ? cardType === 'coordinate'
      ? '服装卡不支持转换'
      : cardType === 'scene'
        ? '场景卡不支持转换'
        : '仅支持 KK/KKS 角色卡'
    : target === 'KKS'
      ? '另存为 KKS (2代)'
      : '另存为 KK (1代)'

  const handleConvert = async () => {
    if (busy || disabled || !cap.canConvert || !target) return
    setBusy(true)
    const res = await backend.convertCard(path, target)
    setBusy(false)
    if (res.ok && res.data) {
      onConverted?.(res.data.savedPath, target)
      onNotify?.(`已转换为 ${target} 并另存为：${res.data.savedPath}`, 'ok')
      onLog?.('ok', 'CONVERT', `${res.data.sourceGame} → ${target}：${res.data.savedPath}`)
    } else {
      const msg = res.error || '卡片转换失败'
      onNotify?.(msg, 'error')
      onLog?.('error', 'CONVERT', msg)
    }
  }

  return (
    <button
      type="button"
      title={
        !cap.canConvert
          ? cap.reason
          : title || `按结构化块转换角色卡并另存为 ${target} 格式，不覆盖原卡`
      }
      disabled={busy || disabled || !cap.canConvert}
      onClick={() => void handleConvert()}
      className={className || 'kk-btn w-full py-1.5 text-[12px]'}
    >
      <ArrowLeftRight size={13} />
      <span>{busy ? '转换中…' : label}</span>
    </button>
  )
}

export const AutoImportPanel: React.FC<{
  pkgDir: string
  onNotify?: NotifyFn
  onLog?: LogFn
}> = ({ pkgDir, onNotify, onLog }) => {
  const [game, setGame] = useState('')
  const [plan, setPlan] = useState<ImportPlan | null>(null)
  const [busy, setBusy] = useState(false)
  const [statusText, setStatusText] = useState('')
  const [statusTone, setStatusTone] = useState<'muted' | 'ok' | 'warn' | 'error'>('muted')
  const [percent, setPercent] = useState(0)
  const [dialog, setDialog] = useState<ConfirmDialogState | null>(null)

  useEffect(() => {
    setPlan(null)
    setStatusText('')
    setStatusTone('muted')
  }, [pkgDir, game])

  const handlePreview = async () => {
    if (!pkgDir.trim()) return
    setBusy(true)
    setStatusTone('muted')
    setStatusText('正在扫描分享包并生成归位预览…')
    setPlan(null)
    const r = await backend.previewAutoImport(pkgDir, game)
    setBusy(false)
    if (r.ok && r.data) {
      setPlan(r.data)
      const msg = `预览完成：可导入 ${r.data.files.length} 项，跳过 ${r.data.skipped.length} 项`
      setStatusTone(r.data.files.length > 0 ? 'ok' : 'warn')
      setStatusText(msg)
      onNotify?.(msg, r.data.files.length > 0 ? 'info' : 'warn')
    } else {
      const msg = r.error || '预览失败'
      setStatusTone('error')
      setStatusText(msg)
      onNotify?.(msg, 'error')
      onLog?.('error', 'AUTO_IMPORT', msg)
    }
  }

  const run = async () => {
    setBusy(true)
    setPercent(5)
    setStatusTone('muted')
    setStatusText('正在复制到已配置的游戏目录…')
    try {
      const r = await backend.startAutoImport(pkgDir, game)
      if (!r.ok || !r.data) {
        const msg = r.error || '导入失败'
        setStatusTone('error')
        setStatusText(msg)
        onNotify?.(msg, 'error')
        onLog?.('error', 'AUTO_IMPORT', msg)
        return
      }
      const done = await waitTask<{
        copied: number
        duplicates: number
        skipped: ImportPlan['skipped']
        errors: ImportPlan['skipped']
      }>(r.data.taskId, (s) => {
        setPercent(s.percent)
        setStatusText(s.message)
      })
      if (!done.ok || !done.data) {
        const msg = done.error || '导入失败'
        setStatusTone('error')
        setStatusText(msg)
        onNotify?.(msg, 'error')
        onLog?.('error', 'AUTO_IMPORT', msg)
        return
      }
      const d = done.data
      const summary = `导入完成：新增 ${d.copied} · 相同文件 ${d.duplicates} · 跳过 ${d.skipped.length} · 失败 ${d.errors.length}`
      const detail = d.errors.map((e) => `\n${e.source}：${e.reason}`).join('')
      const tone = d.errors.length > 0 ? 'warn' : 'ok'
      setStatusTone(tone)
      setStatusText(summary + detail)
      onNotify?.(summary, tone)
      onLog?.(tone === 'warn' ? 'warn' : 'ok', 'AUTO_IMPORT', `${summary} <- ${pkgDir}`)
    } finally {
      setBusy(false)
    }
  }

  const toneColor =
    statusTone === 'ok'
      ? 'var(--success)'
      : statusTone === 'warn'
        ? 'var(--warning)'
        : statusTone === 'error'
          ? 'var(--danger)'
          : 'var(--text-muted)'

  return (
    <div className="flex flex-col gap-3">
      <div className="text-[12px] leading-relaxed" style={{ color: 'var(--text-muted)' }}>
        角色卡按版本与性别归位，服装卡放入 <code className="font-mono-num">coordinate</code>；请先在「外观与设置」配置游戏目录。重名保留两份，相同内容不重复导入。
      </div>

      <label className="flex flex-col gap-1.5 text-[12px]" style={{ color: 'var(--text-muted)' }}>
        <span>场景与 Mod 的目标游戏（角色卡仍按自身版本识别）</span>
        <select
          className="kk-input text-[12.5px]"
          value={game}
          disabled={busy}
          onChange={(e) => setGame(e.target.value)}
        >
          <option value="">暂不导入无法确定版本的文件</option>
          <option value="KK">KK（Koikatsu）</option>
          <option value="KKS">KKS（Koikatsu Sunshine）</option>
        </select>
      </label>

      <div className="flex flex-wrap justify-end gap-2">
        <button
          type="button"
          className="kk-btn"
          disabled={busy || !pkgDir.trim()}
          onClick={() => void handlePreview()}
        >
          <Eye size={14} />
          <span>预览自动归位</span>
        </button>
        <button
          type="button"
          className="kk-btn kk-btn-primary"
          disabled={busy || !plan?.files.length}
          onClick={() =>
            setDialog({
              title: '确认导入到游戏目录',
              message: `将复制 ${plan?.files.length} 项到预览中的游戏目录，跳过 ${plan?.skipped.length} 项。源文件保留，已有文件不覆盖。`,
              confirmLabel: '确认复制',
              onConfirm: () => void run(),
            })
          }
        >
          <FolderInput size={14} />
          <span>确认自动归位</span>
        </button>
      </div>

      {plan && (
        <div className="kk-surface-alt flex max-h-[240px] flex-col gap-2 overflow-y-auto p-3 text-[12px]">
          {plan.files.map((f) => (
            <div
              key={f.source}
              className="flex flex-col gap-0.5 rounded-[var(--radius-sm)] px-2.5 py-2"
              style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
            >
              <div className="flex items-center gap-1.5 break-all">
                <span
                  className="font-mono-num shrink-0 rounded-full px-2 py-0.5 text-[10.5px] font-semibold"
                  style={{ backgroundColor: 'var(--primary-soft)', color: 'var(--primary)' }}
                >
                  {f.game}
                </span>
                <span className="font-mono-num" style={{ color: 'var(--text-strong)' }}>
                  {f.source}
                </span>
              </div>
              <div className="font-mono-num break-all text-[11.5px]" style={{ color: 'var(--text-muted)' }}>
                → {f.target}
              </div>
            </div>
          ))}
          {plan.skipped.map((f) => (
            <div
              key={f.source}
              className="flex flex-col gap-0.5 rounded-[var(--radius-sm)] px-2.5 py-2"
              style={{ backgroundColor: 'var(--warning-soft)', border: '1px solid var(--border)' }}
            >
              <div className="flex items-center gap-1.5 break-all">
                <span
                  className="shrink-0 rounded-full px-2 py-0.5 text-[10.5px] font-semibold"
                  style={{ backgroundColor: 'var(--surface)', color: 'var(--warning)' }}
                >
                  跳过
                </span>
                <span className="font-mono-num" style={{ color: 'var(--text-strong)' }}>
                  {f.source}
                </span>
              </div>
              <div className="text-[11.5px]" style={{ color: 'var(--warning)' }}>
                {f.reason}
              </div>
            </div>
          ))}
        </div>
      )}

      {(busy || statusText) && (
        <div className="kk-surface-alt flex flex-col gap-2 px-3.5 py-2.5 text-[12px]">
          <div className="flex items-center justify-between gap-2">
            <span role="status" className="whitespace-pre-wrap break-all" style={{ color: busy ? 'var(--text-strong)' : toneColor }}>
              {statusText}
            </span>
            {busy && (
              <span className="font-mono-num shrink-0 font-semibold" style={{ color: 'var(--primary)' }}>
                {percent}%
              </span>
            )}
          </div>
          {busy && (
            <div className="kk-progress-bar">
              <div className="kk-progress-fill" style={{ width: `${Math.max(4, percent)}%` }} />
            </div>
          )}
        </div>
      )}

      <ConfirmModal dialog={dialog} onClose={() => setDialog(null)} />
    </div>
  )
}

export const RecoveryPanel: React.FC<{
  onNotify?: NotifyFn
  onLog?: LogFn
}> = ({ onNotify, onLog }) => {
  const [path, setPath] = useState('')
  const [sidecar, setSidecar] = useState('')
  const [outDir, setOutDir] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [resultOk, setResultOk] = useState<boolean | null>(null)
  const [output, setOutput] = useState('')
  const [percent, setPercent] = useState(0)

  const run = async (repair: boolean) => {
    setBusy(true)
    setResultOk(null)
    setMessage(repair ? '正在尝试尾部修复并校验整文件…' : '正在校验文件完整性…')
    setOutput('')
    setPercent(8)
    try {
      let folder = outDir
      if (repair && !folder.trim()) {
        const pick = await backend.pickDirectory('选择修复副本保存目录')
        if (!pick.ok || !pick.data) {
          setMessage(pick.error || '')
          return
        }
        folder = pick.data
        setOutDir(folder)
      }
      const r = await backend.startRecovery({ path, sidecar, outDir: folder, repair })
      if (!r.ok || !r.data) {
        const msg = r.error || '操作失败'
        setResultOk(false)
        setMessage(msg)
        onNotify?.(msg, 'error')
        onLog?.('error', 'RECOVERY', msg)
        return
      }
      const done = await waitTask<{ ok: boolean; reason: string; path?: string }>(
        r.data.taskId,
        (s) => {
          setPercent(s.percent)
          setMessage(s.message)
        },
      )
      if (!done.ok || !done.data) {
        const msg = done.error || '操作失败'
        setResultOk(false)
        setMessage(msg)
        onNotify?.(msg, 'error')
        onLog?.('error', 'RECOVERY', msg)
        return
      }
      const ok = Boolean(done.data.ok)
      const msg = ok ? done.data.reason || '整文件校验通过' : `校验未通过：${done.data.reason}`
      setResultOk(ok)
      setMessage(msg)
      setOutput(done.data.path || '')
      onNotify?.(msg, ok ? 'ok' : 'error')
      onLog?.(ok ? 'ok' : 'error', 'RECOVERY', `${msg} (${path})`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="kk-surface flex flex-col gap-4 p-5">
      <div className="text-[12px] leading-relaxed" style={{ color: 'var(--text-muted)' }}>
        恢复记录须在打包时勾选生成并与产物一起保留；含尾部备份的记录可尝试修复末尾最多 64 KiB 的损坏或截断（分卷请逐卷选择）。修复始终生成新副本，整文件校验通过才保留。
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {[
          { label: '待校验或修复文件', value: path, set: setPath, placeholder: '选择打包产物或单个分卷文件' },
          { label: '恢复记录（留空自动读取同名 .kkrec.json）', value: sidecar, set: setSidecar, placeholder: '可选：手动指定 .kkrec.json' },
        ].map((f) => (
          <label key={f.label} className="flex flex-col gap-1.5 text-[12px]" style={{ color: 'var(--text-muted)' }}>
            <span>{f.label}</span>
            <div className="flex gap-1.5">
              <input
                className="kk-input min-w-0 flex-1 text-[12.5px]"
                value={f.value}
                placeholder={f.placeholder}
                disabled={busy}
                onChange={(e) => f.set(e.target.value)}
              />
              <button
                type="button"
                className="kk-btn px-2.5"
                disabled={busy}
                aria-label={`选择${f.label}`}
                onClick={async () => {
                  const r = await backend.pickAnyFiles(f.label, false)
                  if (r.ok && typeof r.data === 'string') f.set(r.data)
                }}
              >
                <FolderOpen size={14} />
              </button>
            </div>
          </label>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
        <span className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
          原文件只读不改写，超出尾部备份范围的损坏会明确中止报错。
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="kk-btn"
            disabled={busy || !path.trim()}
            onClick={() => void run(false)}
          >
            <ShieldCheck size={14} />
            <span>校验文件</span>
          </button>
          <button
            type="button"
            className="kk-btn kk-btn-primary"
            disabled={busy || !path.trim()}
            onClick={() => void run(true)}
          >
            <Wrench size={14} />
            <span>生成修复副本…</span>
          </button>
        </div>
      </div>

      {(busy || message) && (
        <div className="kk-surface-alt flex flex-col gap-2 px-4 py-3 text-[12.5px]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              {!busy && resultOk === true && (
                <CheckCircle2 size={15} className="shrink-0" style={{ color: 'var(--success)' }} />
              )}
              {!busy && resultOk === false && (
                <AlertTriangle size={15} className="shrink-0" style={{ color: 'var(--danger)' }} />
              )}
              <span
                role="status"
                className="break-all"
                style={{
                  color: busy
                    ? 'var(--text-strong)'
                    : resultOk === true
                      ? 'var(--success)'
                      : resultOk === false
                        ? 'var(--danger)'
                        : 'var(--text-muted)',
                }}
              >
                {message}
              </span>
            </div>
            {busy ? (
              <span className="font-mono-num shrink-0 font-semibold" style={{ color: 'var(--primary)' }}>
                {percent}%
              </span>
            ) : (
              output && (
                <button
                  type="button"
                  className="kk-btn h-7 shrink-0 px-2.5 text-[12px]"
                  onClick={() => void backend.revealInExplorer(output)}
                >
                  <ExternalLink size={12} />
                  <span>查看修复副本</span>
                </button>
              )
            )}
          </div>
          {busy && (
            <div className="kk-progress-bar">
              <div className="kk-progress-fill" style={{ width: `${Math.max(4, percent)}%` }} />
            </div>
          )}
        </div>
      )}
    </section>
  )
}
