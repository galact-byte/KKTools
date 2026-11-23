import { ModExchange } from '../components/ModExchange'
import React, { useMemo, useState } from 'react'
import {
  Archive,
  Clapperboard,
  Download,
  ExternalLink,
  FileArchive,
  FilePlus2,
  FolderInput,
  FolderOpen,
  FolderOutput,
  Layers,
  PackageOpen,
  RefreshCw,
  Search,
  Share2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import { backend, waitTask } from '../lib/bridge'
import type {
  CardModCheckResult,
  LogEntry,
  ModSummaryItem,
  SceneAnalysisResult,
} from '../types/kk'

/* ---- 1. 解包 / 打包页（真实接通 core.stego） ---- */
export const PackPage: React.FC<{
  defaultOutDir: string
  uiMode: 'normal' | 'advanced'
  onNotify: (msg: string, tone?: 'info' | 'ok' | 'warn' | 'error') => void
  onLog: (level: LogEntry['level'], source: string, msg: string) => void
}> = ({ defaultOutDir, uiMode, onNotify, onLog }) => {
  const [mode, setMode] = useState<'pack' | 'unpack'>('pack')
  // 打包态
  const [sources, setSources] = useState<string[]>([])
  const [archiveName, setArchiveName] = useState('KKTools_Pack')
  const [packOutDir, setPackOutDir] = useState(defaultOutDir)
  const [stegoMode, setStegoMode] = useState<'none' | 'image' | 'video'>('none')
  const [carrierPath, setCarrierPath] = useState('')
  const [passwordInput, setPasswordInput] = useState('')
  const [splitMB, setSplitMB] = useState(0)
  const [writeRecovery, setWriteRecovery] = useState(false)

  // 解包态
  const [unpackFile, setUnpackFile] = useState('')
  const [unpackOutDir, setUnpackOutDir] = useState(defaultOutDir)
  const [unpackPasswords, setUnpackPasswords] = useState('')

  // 共享后台任务进度
  const [running, setRunning] = useState(false)
  const [progressPct, setProgressPct] = useState(0)
  const [progressText, setProgressText] = useState('')
  const [lastResultDir, setLastResultDir] = useState('')
  const [resultSummary, setResultSummary] = useState('')

  const handleAddFiles = async () => {
    const res = await backend.pickAnyFiles('选择要打包的文件', true)
    if (res.ok && Array.isArray(res.data) && res.data.length > 0) {
      setSources((prev) => Array.from(new Set([...prev, ...res.data as string[]])))
    }
  }

  const handleAddFolder = async () => {
    const res = await backend.pickDirectory('选择要打包的文件夹')
    if (res.ok && res.data) {
      setSources((prev) => Array.from(new Set([...prev, res.data!])))
    }
  }

  const handleRunPack = async () => {
    if (sources.length === 0) {
      onNotify('请先添加至少一个待打包文件或目录', 'warn')
      return
    }
    let out = packOutDir.trim()
    if (!out) {
      const picked = await backend.pickDirectory('选择打包输出目录')
      if (!picked.ok || !picked.data) return
      out = picked.data
      setPackOutDir(out)
    }

    const pwds = passwordInput
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean)

    setRunning(true)
    setProgressPct(5)
    setProgressText('正在提交打包任务…')
    setResultSummary('')

    const startRes = await backend.startPack({
      sources,
      outDir: out,
      archiveName: archiveName.trim() || 'KKTools_Pack',
      stegoMode,
      carrierPath: carrierPath.trim(),
      passwords: pwds,
      splitMB,
      writeRecovery,
    })

    if (!startRes.ok || !startRes.data) {
      setRunning(false)
      onNotify(`启动打包失败：${startRes.error || '未知错误'}`, 'error')
      onLog('error', 'PACK', `打包失败：${startRes.error}`)
      return
    }

    const done = await waitTask<{ outputs: string[]; outDir: string; recoveryFile: string }>(
      startRes.data.taskId,
      (st) => {
        setProgressPct(st.percent)
        setProgressText(st.message)
      },
    )
    setRunning(false)

    if (!done.ok || !done.data) {
      onNotify(`打包失败：${done.error || '未知错误'}`, 'error')
      onLog('error', 'PACK', `打包失败：${done.error}`)
      return
    }

    setLastResultDir(done.data.outDir)
    const msg = `打包完成：生成 ${done.data.outputs.length} 个产物${done.data.recoveryFile ? '（含恢复记录）' : ''}`
    setResultSummary(msg)
    onNotify(msg, 'ok')
    onLog('ok', 'PACK', `${msg} -> ${done.data.outDir}`)
  }

  const handleRunUnpack = async () => {
    if (!unpackFile.trim()) {
      onNotify('请先选择待解包的压缩包、图种或分卷文件', 'warn')
      return
    }
    let out = unpackOutDir.trim()
    if (!out) {
      const picked = await backend.pickDirectory('选择解包输出目录')
      if (!picked.ok || !picked.data) return
      out = picked.data
      setUnpackOutDir(out)
    }

    const pwds = unpackPasswords
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean)

    setRunning(true)
    setProgressPct(5)
    setProgressText('正在校验并解包…')
    setResultSummary('')

    const startRes = await backend.startUnpack({
      inputPath: unpackFile.trim(),
      outDir: out,
      passwords: pwds,
    })
    if (!startRes.ok || !startRes.data) {
      setRunning(false)
      onNotify(`启动解包失败：${startRes.error || '未知错误'}`, 'error')
      onLog('error', 'UNPACK', `解包失败：${startRes.error}`)
      return
    }

    const done = await waitTask<{ count: number; outDir: string }>(startRes.data.taskId, (st) => {
      setProgressPct(st.percent)
      setProgressText(st.message)
    })
    setRunning(false)

    if (!done.ok || !done.data) {
      onNotify(`解包失败：${done.error || '请检查密码或分卷完整性'}`, 'error')
      onLog('error', 'UNPACK', `解包失败：${done.error}`)
      return
    }

    setLastResultDir(done.data.outDir)
    const msg = `解包完成：成功提取 ${done.data.count} 个文件`
    setResultSummary(msg)
    onNotify(msg, 'ok')
    onLog('ok', 'UNPACK', `${msg} -> ${done.data.outDir}`)
  }

  return (
    <div className="h-full overflow-y-auto px-5 py-4">
      <div className="mx-auto flex max-w-[1020px] flex-col gap-4 pb-6">
        <div className="kk-surface flex flex-wrap items-center justify-between gap-3 p-4">
          <div className="flex items-center gap-2">
            {(
              [
                { id: 'pack', label: '打包成分享包', icon: Archive },
                { id: 'unpack', label: '解包 / 还原分卷', icon: PackageOpen },
              ] as const
            ).map(({ id, label, icon: Icon }) => {
              const active = mode === id
              return (
                <button
                  key={id}
                  type="button"
                  disabled={running}
                  onClick={() => setMode(id)}
                  className="inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[13px] font-semibold transition-colors cursor-pointer"
                  style={{
                    backgroundColor: active ? 'var(--primary)' : 'var(--surface-alt)',
                    color: active ? 'var(--on-primary)' : 'var(--text)',
                    border: `1px solid ${active ? 'var(--primary)' : 'var(--border)'}`,
                  }}
                >
                  <Icon size={14} />
                  <span>{label}</span>
                </button>
              )
            })}
          </div>
          <span className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
            已直连 <code className="font-mono-num">core.stego</code> · 支持图种/视频伪装、多层加密与分卷完整性校验
          </span>
        </div>

        <div key={mode} className="kk-tab-enter">
          {mode === 'pack' ? (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.15fr_1fr]">
              {/* 左侧待打包清单 */}
              <section className="kk-surface flex flex-col gap-3 p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[14px] font-semibold" style={{ color: 'var(--text-strong)' }}>
                    待打包文件队列 ({sources.length})
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button type="button" disabled={running} onClick={handleAddFiles} className="kk-btn text-[12px]">
                      <FilePlus2 size={13} />
                      <span>添加文件</span>
                    </button>
                    <button type="button" disabled={running} onClick={handleAddFolder} className="kk-btn text-[12px]">
                      <FolderOpen size={13} />
                      <span>添加文件夹</span>
                    </button>
                    {sources.length > 0 && (
                      <button
                        type="button"
                        disabled={running}
                        onClick={() => setSources([])}
                        className="kk-btn kk-btn-danger px-2 text-[12px]"
                        title="清空队列"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                </div>

                {sources.length === 0 ? (
                  <div
                    className="flex min-h-[260px] flex-col items-center justify-center gap-2.5 rounded-[var(--radius-md)] border-2 border-dashed p-6 text-center"
                    style={{ borderColor: 'var(--border-strong)', backgroundColor: 'var(--surface-alt)' }}
                  >
                    <FileArchive size={28} style={{ color: 'var(--primary)' }} />
                    <div className="text-[14px] font-semibold" style={{ color: 'var(--text-strong)' }}>
                      添加角色卡、zipmod 或整个目录
                    </div>
                    <p className="max-w-xs text-[12px]" style={{ color: 'var(--text-muted)' }}>
                      单个文件夹将保持内部目录结构打包，多个文件自动归拢入同一分享包。
                    </p>
                  </div>
                ) : (
                  <div className="flex max-h-[300px] flex-col gap-1.5 overflow-y-auto pr-1">
                    {sources.map((src) => (
                      <div
                        key={src}
                        className="kk-surface-alt flex items-center justify-between gap-2 px-3 py-2 text-[12px]"
                      >
                        <span className="font-mono-num truncate" style={{ color: 'var(--text-strong)' }} title={src}>
                          {src}
                        </span>
                        <button
                          type="button"
                          disabled={running}
                          onClick={() => setSources((prev) => prev.filter((x) => x !== src))}
                          className="kk-btn-ghost flex h-6 w-6 shrink-0 items-center justify-center rounded-[5px] cursor-pointer"
                          aria-label="移除"
                        >
                          <X size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* 右侧打包配置 */}
              <section className="kk-surface flex flex-col justify-between gap-4 p-5">
                <div className="flex flex-col gap-3.5">
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <label className="flex flex-col gap-1">
                      <span className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
                        输出文件名
                      </span>
                      <input
                        type="text"
                        value={archiveName}
                        onChange={(e) => setArchiveName(e.target.value)}
                        className="kk-input text-[12.5px]"
                      />
                    </label>

                    <div className="flex flex-col gap-1">
                      <span className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
                        输出目录
                      </span>
                      <div className="flex gap-1.5">
                        <input
                          type="text"
                          value={packOutDir}
                          onChange={(e) => setPackOutDir(e.target.value)}
                          placeholder="未选择"
                          className="kk-input flex-1 text-[12px]"
                        />
                        <button
                          type="button"
                          onClick={async () => {
                            const r = await backend.pickDirectory('选择打包输出目录', packOutDir)
                            if (r.ok && r.data) setPackOutDir(r.data)
                          }}
                          className="kk-btn px-2.5"
                        >
                          <FolderOpen size={14} />
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <span className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
                      伪装方式
                    </span>
                    <div className="grid grid-cols-3 gap-2">
                      {(
                        [
                          { id: 'none', label: '标准 ZIP' },
                          { id: 'image', label: '图片图种' },
                          { id: 'video', label: '视频载体' },
                        ] as const
                      ).map((item) => {
                        const active = stegoMode === item.id
                        return (
                          <button
                            key={item.id}
                            type="button"
                            onClick={() => setStegoMode(item.id)}
                            className="rounded-[var(--radius-sm)] py-2 text-[12.5px] font-medium cursor-pointer"
                            style={{
                              backgroundColor: active ? 'var(--primary-soft)' : 'var(--surface-alt)',
                              border: `1px solid ${active ? 'var(--primary-border)' : 'var(--border)'}`,
                              color: active ? 'var(--primary)' : 'var(--text-muted)',
                            }}
                          >
                            {item.label}
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  {stegoMode !== 'none' && (
                    <div className="flex flex-col gap-1">
                      <span className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
                        载体文件（留空则自动从设置中的载体目录随机抽取）
                      </span>
                      <div className="flex gap-1.5">
                        <input
                          type="text"
                          value={carrierPath}
                          onChange={(e) => setCarrierPath(e.target.value)}
                          placeholder="可选：手动指定一张图片或视频"
                          className="kk-input flex-1 text-[12px]"
                        />
                        <button
                          type="button"
                          onClick={async () => {
                            const r =
                              stegoMode === 'image'
                                ? await backend.pickImageFile('选择图片载体')
                                : await backend.pickAnyFiles('选择视频载体', false)
                            if (r.ok && typeof r.data === 'string' && r.data) setCarrierPath(r.data)
                          }}
                          className="kk-btn px-2.5"
                        >
                          <FolderOpen size={14} />
                        </button>
                      </div>
                    </div>
                  )}

                  <label className="flex flex-col gap-1">
                    <span className="flex items-center gap-1.5 text-[12px]" style={{ color: 'var(--text-muted)' }}>
                      <ShieldCheck size={13} style={{ color: 'var(--primary)' }} />
                      密码保护（留空不加密；多行填多个密码自动启用套娃多层加密）
                    </span>
                    <textarea
                      rows={uiMode === 'advanced' ? 2 : 1}
                      value={passwordInput}
                      onChange={(e) => setPasswordInput(e.target.value)}
                      placeholder="可选：输入解压密码"
                      className="kk-input resize-none text-[12.5px]"
                    />
                  </label>

                  <label className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between text-[12px]">
                      <span style={{ color: 'var(--text-muted)' }}>单卷体积上限（0 表示不分卷）</span>
                      <span className="font-mono-num font-semibold" style={{ color: 'var(--primary)' }}>
                        {splitMB === 0 ? '不分卷' : `${splitMB} MB`}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={200}
                      step={10}
                      value={splitMB}
                      onChange={(e) => setSplitMB(Number(e.target.value))}
                      className="w-full accent-[var(--primary)]"
                    />
                  </label>

                  {uiMode === 'advanced' && (
                    <label className="flex cursor-pointer items-center gap-2 text-[12.5px]" style={{ color: 'var(--text)' }}>
                      <input
                        type="checkbox"
                        checked={writeRecovery}
                        onChange={(e) => setWriteRecovery(e.target.checked)}
                        className="h-3.5 w-3.5 accent-[var(--primary)]"
                      />
                      <span>附带恢复校验记录（.kkrec sidecar）</span>
                    </label>
                  )}
                </div>

                <button
                  type="button"
                  disabled={running}
                  onClick={() => void handleRunPack()}
                  className="kk-btn kk-btn-primary w-full py-2.5"
                >
                  <Archive size={14} />
                  <span>{running ? '打包处理中…' : '开始生成分享包'}</span>
                </button>
              </section>
            </div>
          ) : (
            <section className="kk-surface flex flex-col gap-4 p-5">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <span className="text-[12px] font-medium" style={{ color: 'var(--text-muted)' }}>
                    待解包文件（ZIP / 图种 / 视频载体 / 首个分卷）
                  </span>
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      value={unpackFile}
                      onChange={(e) => setUnpackFile(e.target.value)}
                      placeholder="选择要解包或合并还原的文件"
                      className="kk-input flex-1 text-[12.5px]"
                    />
                    <button
                      type="button"
                      onClick={async () => {
                        const r = await backend.pickAnyFiles('选择待解包文件', false)
                        if (r.ok && typeof r.data === 'string' && r.data) setUnpackFile(r.data)
                      }}
                      className="kk-btn px-2.5"
                    >
                      <FolderOpen size={14} />
                    </button>
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <span className="text-[12px] font-medium" style={{ color: 'var(--text-muted)' }}>
                    解压目标目录
                  </span>
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      value={unpackOutDir}
                      onChange={(e) => setUnpackOutDir(e.target.value)}
                      placeholder="选择输出目录"
                      className="kk-input flex-1 text-[12.5px]"
                    />
                    <button
                      type="button"
                      onClick={async () => {
                        const r = await backend.pickDirectory('选择解压输出目录', unpackOutDir)
                        if (r.ok && r.data) setUnpackOutDir(r.data)
                      }}
                      className="kk-btn px-2.5"
                    >
                      <FolderOpen size={14} />
                    </button>
                  </div>
                </div>
              </div>

              <label className="flex flex-col gap-1.5">
                <span className="text-[12px] font-medium" style={{ color: 'var(--text-muted)' }}>
                  解压密码（可选；每行一个密码，支持自动尝试或按顺序解多层加密）
                </span>
                <textarea
                  rows={2}
                  value={unpackPasswords}
                  onChange={(e) => setUnpackPasswords(e.target.value)}
                  placeholder="无密码可留空"
                  className="kk-input resize-none text-[12.5px]"
                />
              </label>

              <div className="flex items-center justify-between pt-1">
                <span className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
                  遇到分卷会自动校验卷号连续完整，缺任一卷即中止报错，绝不静默产残包。
                </span>
                <button
                  type="button"
                  disabled={running}
                  onClick={() => void handleRunUnpack()}
                  className="kk-btn kk-btn-primary"
                >
                  <PackageOpen size={14} />
                  <span>{running ? '解包校验中…' : '开始校验并解包'}</span>
                </button>
              </div>
            </section>
          )}
        </div>

        {/* 进度与结果反馈条 */}
        {(running || resultSummary) && (
          <div className="kk-surface flex flex-col gap-2 p-4 text-[12.5px]">
            <div className="flex items-center justify-between gap-2">
              <span style={{ color: running ? 'var(--text-strong)' : 'var(--success)' }}>
                {running ? progressText : resultSummary}
              </span>
              {running ? (
                <span className="font-mono-num font-semibold" style={{ color: 'var(--primary)' }}>
                  {progressPct}%
                </span>
              ) : (
                lastResultDir && (
                  <button
                    type="button"
                    onClick={() => void backend.revealInExplorer(lastResultDir)}
                    className="kk-btn h-7 px-2.5 text-[12px]"
                  >
                    <ExternalLink size={12} />
                    <span>打开输出目录</span>
                  </button>
                )
              )}
            </div>
            {running && (
              <div className="kk-progress-bar">
                <div className="kk-progress-fill" style={{ width: `${Math.max(4, progressPct)}%` }} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/* ---- 2. 分享整理页（真实接通 core.share） ---- */
export const SharePage: React.FC<{
  defaultOutDir: string
  onNotify: (msg: string, tone?: 'info' | 'ok' | 'warn' | 'error') => void
  onLog: (level: LogEntry['level'], source: string, msg: string) => void
}> = ({ defaultOutDir, onNotify, onLog }) => {
  const [tab, setTab] = useState<'export' | 'import' | 'organize'>('export')
  // 导出态
  const [cardPaths, setCardPaths] = useState<string[]>([])
  const [exportOutDir, setExportOutDir] = useState(defaultOutDir)
  const [groupByChar, setGroupByChar] = useState(true)
  const [excludeGuids, setExcludeGuids] = useState('')

  // 导入态
  const [pkgDir, setPkgDir] = useState('')
  const [cardTarget, setCardTarget] = useState('')
  const [modTarget, setModTarget] = useState('')

  // 目录整理态
  const [orgSrc, setOrgSrc] = useState('')
  const [orgOut, setOrgOut] = useState(defaultOutDir)
  const [orgBy, setOrgBy] = useState<'type' | 'game'>('type')
  const [orgMove, setOrgMove] = useState(false)

  const [running, setRunning] = useState(false)
  const [progressPct, setProgressPct] = useState(0)
  const [progressText, setProgressText] = useState('')
  const [reportText, setReportText] = useState('')
  const [resultDir, setResultDir] = useState('')

  const runExport = async () => {
    if (cardPaths.length === 0) {
      onNotify('请先添加至少一张要分享的角色卡', 'warn')
      return
    }
    let out = exportOutDir.trim()
    if (!out) {
      const r = await backend.pickDirectory('选择分享包输出目录')
      if (!r.ok || !r.data) return
      out = r.data
      setExportOutDir(out)
    }

    setRunning(true)
    setProgressPct(8)
    setProgressText('正在分析角色卡并整理依赖 Mod…')
    setReportText('')

    const startRes = await backend.startShareExport({
      cardPaths,
      outDir: out,
      groupByChar,
      excludeGuids,
    })
    if (!startRes.ok || !startRes.data) {
      setRunning(false)
      onNotify(`导出失败：${startRes.error}`, 'error')
      return
    }
    const done = await waitTask<{ report: Record<string, unknown>; outDir: string }>(
      startRes.data.taskId,
      (st) => {
        setProgressPct(st.percent)
        setProgressText(st.message)
      },
    )
    setRunning(false)
    if (!done.ok || !done.data) {
      onNotify(`分享导出失败：${done.error}`, 'error')
      onLog('error', 'SHARE', `导出失败：${done.error}`)
      return
    }
    const rep = done.data.report
    const summary = `导出完成：卡片 ${Array.isArray(rep.cards) ? rep.cards.length : cardPaths.length} 张 · 打包 Mod ${Array.isArray(rep.copied_mods) ? rep.copied_mods.length : 0} 项 · 缺失 ${Array.isArray(rep.total_missing) ? rep.total_missing.length : 0} 项`
    setReportText(summary)
    setResultDir(done.data.outDir)
    onNotify(summary, 'ok')
    onLog('ok', 'SHARE', `${summary} -> ${done.data.outDir}`)
  }

  const runImport = async () => {
    if (!pkgDir.trim() || !cardTarget.trim()) {
      onNotify('请选择分享包目录与角色卡导入目标目录', 'warn')
      return
    }
    setRunning(true)
    setProgressPct(10)
    setProgressText('正在还原分享包…')
    setReportText('')

    const startRes = await backend.startShareImport({
      pkgDir: pkgDir.trim(),
      cardTarget: cardTarget.trim(),
      modTarget: modTarget.trim() || undefined,
    })
    if (!startRes.ok || !startRes.data) {
      setRunning(false)
      onNotify(`导入失败：${startRes.error}`, 'error')
      return
    }
    const done = await waitTask<{ report: Record<string, unknown>; cardTarget: string }>(
      startRes.data.taskId,
      (st) => {
        setProgressPct(st.percent)
        setProgressText(st.message)
      },
    )
    setRunning(false)
    if (!done.ok || !done.data) {
      onNotify(`导入失败：${done.error}`, 'error')
      onLog('error', 'SHARE', `导入失败：${done.error}`)
      return
    }
    const rep = done.data.report
    const summary = `导入完成：还原卡片 ${rep.cards ?? 0} 张 · Mod ${rep.mods ?? 0} 项 · 跳过已有卡片 ${rep.cards_skipped ?? 0} 张`
    setReportText(summary)
    setResultDir(done.data.cardTarget)
    onNotify(summary, 'ok')
    onLog('ok', 'SHARE', summary)
  }

  const runOrganize = async () => {
    if (!orgSrc.trim() || !orgOut.trim()) {
      onNotify('请选择源目录与输出目录', 'warn')
      return
    }
    setRunning(true)
    setProgressPct(10)
    setProgressText('正在按分类整理卡片…')
    setReportText('')
    const startRes = await backend.startOrganizeCards({
      srcDir: orgSrc.trim(),
      outDir: orgOut.trim(),
      by: orgBy,
      move: orgMove,
    })
    if (!startRes.ok || !startRes.data) {
      setRunning(false)
      onNotify(`整理失败：${startRes.error}`, 'error')
      return
    }
    const done = await waitTask<{ report: Record<string, unknown>; outDir: string }>(
      startRes.data.taskId,
      (st) => {
        setProgressPct(st.percent)
        setProgressText(st.message)
      },
    )
    setRunning(false)
    if (!done.ok || !done.data) {
      onNotify(`整理失败：${done.error}`, 'error')
      return
    }
    const summary = `整理完成：处理完成，结果已输出至目标目录`
    setReportText(summary)
    setResultDir(done.data.outDir)
    onNotify(summary, 'ok')
    onLog('ok', 'SHARE', `${summary} (${done.data.outDir})`)
  }

  return (
    <div className="h-full overflow-y-auto px-5 py-4">
      <div className="mx-auto flex max-w-[1000px] flex-col gap-4 pb-6">
        <div className="kk-surface flex flex-wrap items-center justify-between gap-2 p-4">
          <div className="flex items-center gap-2">
            {(
              [
                { id: 'export', label: '整理导出分享包', icon: FolderOutput },
                { id: 'import', label: '导入分享包', icon: FolderInput },
                { id: 'organize', label: '分类整理目录', icon: Sparkles },
              ] as const
            ).map(({ id, label, icon: Icon }) => {
              const active = tab === id
              return (
                <button
                  key={id}
                  type="button"
                  disabled={running}
                  onClick={() => setTab(id)}
                  className="inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[13px] font-semibold transition-colors cursor-pointer"
                  style={{
                    backgroundColor: active ? 'var(--primary)' : 'var(--surface-alt)',
                    color: active ? 'var(--on-primary)' : 'var(--text)',
                    border: `1px solid ${active ? 'var(--primary)' : 'var(--border)'}`,
                  }}
                >
                  <Icon size={14} />
                  <span>{label}</span>
                </button>
              )
            })}
          </div>
          <span className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
            同名卡自动防覆盖保留 · 完整提取依赖 Mod 与清单
          </span>
        </div>

        <div key={tab} className="kk-tab-enter">
          {tab === 'export' && (
            <section className="kk-surface flex flex-col gap-4 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-[14px] font-semibold" style={{ color: 'var(--text-strong)' }}>
                  已选角色卡 ({cardPaths.length})
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={running}
                    onClick={async () => {
                      const r = await backend.pickCardFiles('批量选择要分享的角色卡')
                      if (r.ok && r.data && r.data.length > 0) {
                        setCardPaths((prev) => Array.from(new Set([...prev, ...r.data!])))
                      }
                    }}
                    className="kk-btn text-[12px]"
                  >
                    <FilePlus2 size={13} />
                    <span>批量添加角色卡</span>
                  </button>
                  {cardPaths.length > 0 && (
                    <button
                      type="button"
                      disabled={running}
                      onClick={() => setCardPaths([])}
                      className="kk-btn kk-btn-danger px-2 text-[12px]"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              </div>

              {cardPaths.length > 0 && (
                <div className="flex max-h-40 flex-col gap-1 overflow-y-auto">
                  {cardPaths.map((p) => (
                    <div key={p} className="kk-surface-alt flex items-center justify-between px-3 py-1.5 text-[12px]">
                      <span className="font-mono-num truncate" style={{ color: 'var(--text-strong)' }}>
                        {p}
                      </span>
                      <button
                        type="button"
                        onClick={() => setCardPaths((prev) => prev.filter((x) => x !== p))}
                        className="kk-btn-ghost flex h-6 w-6 items-center justify-center rounded-[5px] cursor-pointer"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <span className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
                    分享包输出目录
                  </span>
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      value={exportOutDir}
                      onChange={(e) => setExportOutDir(e.target.value)}
                      placeholder="选择输出目录"
                      className="kk-input flex-1 text-[12.5px]"
                    />
                    <button
                      type="button"
                      onClick={async () => {
                        const r = await backend.pickDirectory('选择分享包输出目录', exportOutDir)
                        if (r.ok && r.data) setExportOutDir(r.data)
                      }}
                      className="kk-btn px-2.5"
                    >
                      <FolderOpen size={14} />
                    </button>
                  </div>
                </div>

                <label className="kk-surface-alt flex cursor-pointer items-center justify-between px-3.5 py-2.5 text-[13px]">
                  <span style={{ color: 'var(--text-strong)' }}>按角色分文件夹归类</span>
                  <input
                    type="checkbox"
                    checked={groupByChar}
                    onChange={(e) => setGroupByChar(e.target.checked)}
                    className="h-4 w-4 accent-[var(--primary)]"
                  />
                </label>
              </div>

              <label className="flex flex-col gap-1">
                <span className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
                  排除的通用基础 Mod GUID（可选，每行一个）
                </span>
                <textarea
                  rows={2}
                  value={excludeGuids}
                  onChange={(e) => setExcludeGuids(e.target.value)}
                  placeholder="例如不想重复打包的大型公共基础包 GUID"
                  className="kk-input resize-none font-mono-num text-[12px]"
                />
              </label>

              <div className="flex justify-end">
                <button
                  type="button"
                  disabled={running}
                  onClick={() => void runExport()}
                  className="kk-btn kk-btn-primary"
                >
                  <Share2 size={14} />
                  <span>{running ? '整理导出中…' : '开始导出分享包'}</span>
                </button>
              </div>
            </section>
          )}

          {tab === 'import' && (
            <section className="kk-surface flex flex-col gap-4 p-5">
              {(
                [
                  { label: '分享包所在目录', val: pkgDir, set: setPkgDir },
                  { label: '角色卡还原目标目录（如 UserData/chara/female）', val: cardTarget, set: setCardTarget },
                  { label: 'Mod 还原目标目录（可选，如游戏 mods 目录）', val: modTarget, set: setModTarget },
                ] as const
              ).map((item) => (
                <div key={item.label} className="flex flex-col gap-1.5">
                  <span className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
                    {item.label}
                  </span>
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      value={item.val}
                      onChange={(e) => item.set(e.target.value)}
                      className="kk-input flex-1 text-[12.5px]"
                    />
                    <button
                      type="button"
                      onClick={async () => {
                        const r = await backend.pickDirectory(item.label, item.val)
                        if (r.ok && r.data) item.set(r.data)
                      }}
                      className="kk-btn px-2.5"
                    >
                      <FolderOpen size={14} />
                    </button>
                  </div>
                </div>
              ))}
              <div className="flex justify-end">
                <button
                  type="button"
                  disabled={running}
                  onClick={() => void runImport()}
                  className="kk-btn kk-btn-primary"
                >
                  <FolderInput size={14} />
                  <span>{running ? '还原导入中…' : '开始导入分享包'}</span>
                </button>
              </div>
            </section>
          )}

          {tab === 'organize' && (
            <section className="kk-surface flex flex-col gap-4 p-5">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <span className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
                    待整理卡片源目录
                  </span>
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      value={orgSrc}
                      onChange={(e) => setOrgSrc(e.target.value)}
                      className="kk-input flex-1 text-[12.5px]"
                    />
                    <button
                      type="button"
                      onClick={async () => {
                        const r = await backend.pickDirectory('选择源目录', orgSrc)
                        if (r.ok && r.data) setOrgSrc(r.data)
                      }}
                      className="kk-btn px-2.5"
                    >
                      <FolderOpen size={14} />
                    </button>
                  </div>
                </div>
                <div className="flex flex-col gap-1.5">
                  <span className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
                    分类输出目录
                  </span>
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      value={orgOut}
                      onChange={(e) => setOrgOut(e.target.value)}
                      className="kk-input flex-1 text-[12.5px]"
                    />
                    <button
                      type="button"
                      onClick={async () => {
                        const r = await backend.pickDirectory('选择输出目录', orgOut)
                        if (r.ok && r.data) setOrgOut(r.data)
                      }}
                      className="kk-btn px-2.5"
                    >
                      <FolderOpen size={14} />
                    </button>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5">
                    {(['type', 'game'] as const).map((by) => (
                      <button
                        key={by}
                        type="button"
                        onClick={() => setOrgBy(by)}
                        className="rounded-full px-3 py-1 text-[12.5px] font-medium cursor-pointer"
                        style={{
                          backgroundColor: orgBy === by ? 'var(--primary-soft)' : 'var(--surface-alt)',
                          border: `1px solid ${orgBy === by ? 'var(--primary-border)' : 'var(--border)'}`,
                          color: orgBy === by ? 'var(--primary)' : 'var(--text-muted)',
                        }}
                      >
                        {by === 'type' ? '按卡片类型分组' : '按游戏版本 (KK/KKS) 分组'}
                      </button>
                    ))}
                  </div>

                  <label className="flex cursor-pointer items-center gap-1.5 text-[12.5px]" style={{ color: 'var(--text)' }}>
                    <input
                      type="checkbox"
                      checked={orgMove}
                      onChange={(e) => setOrgMove(e.target.checked)}
                      className="h-3.5 w-3.5 accent-[var(--primary)]"
                    />
                    <span>移动原文件（不勾选则安全复制）</span>
                  </label>
                </div>

                <button
                  type="button"
                  disabled={running}
                  onClick={() => void runOrganize()}
                  className="kk-btn kk-btn-primary"
                >
                  <Sparkles size={14} />
                  <span>{running ? '整理中…' : '开始分类整理'}</span>
                </button>
              </div>
            </section>
          )}
        </div>

        {(running || reportText) && (
          <div className="kk-surface flex flex-col gap-2 p-4 text-[12.5px]">
            <div className="flex items-center justify-between gap-2">
              <span style={{ color: running ? 'var(--text-strong)' : 'var(--success)' }}>
                {running ? progressText : reportText}
              </span>
              {running ? (
                <span className="font-mono-num font-semibold" style={{ color: 'var(--primary)' }}>
                  {progressPct}%
                </span>
              ) : (
                resultDir && (
                  <button
                    type="button"
                    onClick={() => void backend.revealInExplorer(resultDir)}
                    className="kk-btn h-7 px-2.5 text-[12px]"
                  >
                    <ExternalLink size={12} />
                    <span>打开目录</span>
                  </button>
                )
              )}
            </div>
            {running && (
              <div className="kk-progress-bar">
                <div className="kk-progress-fill" style={{ width: `${Math.max(4, progressPct)}%` }} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/* ---- 3. Mod 仓库页（完整接通 core.mod_index：扫描/缺失检测/导出 GUID/未引用归档/按作者整理） ---- */
export const ModPage: React.FC<{
  mods: ModSummaryItem[]
  scanning: boolean
  scanProgress: string
  modDirs: string[]
  onScanMods: () => void
  onNotify: (msg: string, tone?: 'info' | 'ok' | 'warn' | 'error') => void
  onLog: (level: LogEntry['level'], source: string, msg: string) => void
}> = ({ mods, scanning, scanProgress, modDirs, onScanMods, onNotify, onLog }) => {
  const [keyword, setKeyword] = useState('')
  const [checkResult, setCheckResult] = useState<CardModCheckResult | null>(null)
  const [toolBusy, setToolBusy] = useState(false)
  const [toolMsg, setToolMsg] = useState('')

  const filtered = useMemo(() => {
    const q = keyword.trim().toLowerCase()
    if (!q) return mods
    return mods.filter(
      (m) =>
        m.name.toLowerCase().includes(q) ||
        m.guid.toLowerCase().includes(q) ||
        m.author.toLowerCase().includes(q) ||
        m.fileName.toLowerCase().includes(q),
    )
  }, [mods, keyword])

  const handleCheckCard = async () => {
    const pick = await backend.pickCardFile('选择一张角色卡检测 Mod 缺失')
    if (!pick.ok || !pick.data) return
    const res = await backend.checkCardMods(pick.data)
    if (!res.ok || !res.data) {
      onNotify(`检测失败：${res.error}`, 'error')
      return
    }
    setCheckResult(res.data)
    onNotify(
      `检测完成：已就绪 ${res.data.present.length} 项，缺失 ${res.data.missing.length} 项`,
      res.data.missing.length > 0 ? 'warn' : 'ok',
    )
  }

  const handleExportGuids = async () => {
    const save = await backend.pickSaveTxt('导出本地 Mod GUID 列表')
    if (!save.ok || !save.data) return
    const res = await backend.exportModGuids(save.data)
    if (!res.ok || !res.data) {
      onNotify(`导出失败：${res.error}`, 'error')
      return
    }
    onNotify(`已导出 ${res.data.count} 条 GUID 到 ${res.data.path}`, 'ok')
    onLog('ok', 'MOD', `导出 GUID 列表：${res.data.count} 条 -> ${res.data.path}`)
  }

  const handleArchiveUnreferenced = async () => {
    const cardDirRes = await backend.pickDirectory('第 1 步：选择角色卡目录（分析全部引用）')
    if (!cardDirRes.ok || !cardDirRes.data) return
    const archDirRes = await backend.pickDirectory('第 2 步：选择未引用 Mod 归档输出目录（安全复制）')
    if (!archDirRes.ok || !archDirRes.data) return

    setToolBusy(true)
    setToolMsg('正在严格全量校验所有角色卡并归档未引用 Mod…')
    const startRes = await backend.startArchiveUnreferenced({
      cardDir: cardDirRes.data,
      archiveDir: archDirRes.data,
      move: false,
    })
    if (!startRes.ok || !startRes.data) {
      setToolBusy(false)
      onNotify(`归档失败：${startRes.error}`, 'error')
      return
    }
    const done = await waitTask<{ report: Record<string, unknown>; archiveDir: string }>(
      startRes.data.taskId,
      (st) => setToolMsg(st.message),
    )
    setToolBusy(false)
    if (!done.ok || !done.data) {
      onNotify(`未引用归档已中止：${done.error}`, 'error')
      onLog('error', 'MOD', `未引用归档中止：${done.error}`)
      return
    }
    const msg = `归档完成：结果已安全复制到 ${done.data.archiveDir}`
    setToolMsg(msg)
    onNotify(msg, 'ok')
    onLog('ok', 'MOD', msg)
  }

  const handleOrganizeAuthor = async () => {
    const outRes = await backend.pickDirectory('选择按作者整理输出目录（安全复制）')
    if (!outRes.ok || !outRes.data) return
    setToolBusy(true)
    setToolMsg('正在按作者分组整理 Mod…')
    const startRes = await backend.startOrganizeMods({ targetDir: outRes.data, move: false })
    if (!startRes.ok || !startRes.data) {
      setToolBusy(false)
      onNotify(`整理失败：${startRes.error}`, 'error')
      return
    }
    const done = await waitTask<{ report: Record<string, unknown>; targetDir: string }>(
      startRes.data.taskId,
      (st) => setToolMsg(st.message),
    )
    setToolBusy(false)
    if (!done.ok || !done.data) {
      onNotify(`按作者整理失败：${done.error}`, 'error')
      return
    }
    const msg = `按作者整理完成：已输出至 ${done.data.targetDir}`
    setToolMsg(msg)
    onNotify(msg, 'ok')
    onLog('ok', 'MOD', msg)
  }

  return (
    <div className="flex h-full flex-col gap-3.5 overflow-hidden px-5 py-4">
      <ModExchange notify={onNotify} />
      <div className="kk-surface flex shrink-0 flex-wrap items-center justify-between gap-2.5 p-3.5">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative w-60">
            <Search
              size={14}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
              style={{ color: 'var(--text-dim)' }}
            />
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="按 GUID / 名称 / 作者筛选..."
              className="kk-input h-8 py-1 pl-8 text-[12.5px]"
            />
          </div>
          <span className="font-mono-num text-[12px]" style={{ color: 'var(--text-muted)' }}>
            {scanning ? scanProgress || '正在扫描…' : `已索引 ${filtered.length} / ${mods.length}`}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <button type="button" disabled={scanning || toolBusy} onClick={() => void handleCheckCard()} className="kk-btn text-[12px]">
            <ShieldAlert size={13} />
            <span>检测角色卡缺失</span>
          </button>
          <button type="button" disabled={scanning || toolBusy || mods.length === 0} onClick={() => void handleExportGuids()} className="kk-btn text-[12px]">
            <Download size={13} />
            <span>导出 GUID</span>
          </button>
          <button type="button" disabled={scanning || toolBusy || mods.length === 0} onClick={() => void handleArchiveUnreferenced()} className="kk-btn text-[12px]">
            <Archive size={13} />
            <span>归档未引用</span>
          </button>
          <button type="button" disabled={scanning || toolBusy || mods.length === 0} onClick={() => void handleOrganizeAuthor()} className="kk-btn text-[12px]">
            <FolderOutput size={13} />
            <span>按作者整理</span>
          </button>
          <button type="button" disabled={scanning || toolBusy} onClick={onScanMods} className="kk-btn kk-btn-primary text-[12px]">
            <RefreshCw size={13} className={scanning ? 'animate-spin' : ''} />
            <span>{scanning ? '索引中…' : '扫描仓库'}</span>
          </button>
        </div>
      </div>

      {toolMsg && (
        <div className="kk-surface flex shrink-0 items-center justify-between px-4 py-2 text-[12.5px]">
          <span style={{ color: 'var(--text-strong)' }}>{toolMsg}</span>
          {!toolBusy && (
            <button type="button" onClick={() => setToolMsg('')} className="kk-btn-ghost cursor-pointer p-1">
              <X size={13} />
            </button>
          )}
        </div>
      )}

      {checkResult && (
        <div className="kk-surface flex shrink-0 flex-col gap-2 p-3.5 text-[12.5px]">
          <div className="flex items-center justify-between">
            <span style={{ color: 'var(--text-strong)' }}>
              缺失检测 · 已装 <strong className="font-mono-num" style={{ color: 'var(--success)' }}>{checkResult.present.length}</strong> / 缺失{' '}
              <strong className="font-mono-num" style={{ color: checkResult.missing.length > 0 ? 'var(--danger)' : 'var(--success)' }}>
                {checkResult.missing.length}
              </strong>
            </span>
            <button type="button" onClick={() => setCheckResult(null)} className="kk-btn-ghost cursor-pointer p-1">
              <X size={13} />
            </button>
          </div>
          {checkResult.missing.length > 0 && (
            <div className="flex max-h-24 flex-wrap gap-1.5 overflow-y-auto">
              {checkResult.missing.map((g) => (
                <code
                  key={g}
                  className="font-mono-num rounded-[5px] px-2 py-0.5 text-[11px]"
                  style={{ backgroundColor: 'var(--danger-soft)', color: 'var(--danger)' }}
                >
                  {g}
                </code>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="kk-surface flex min-h-0 flex-1 flex-col overflow-hidden">
        {filtered.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2.5 p-8 text-center">
            <Layers size={26} style={{ color: 'var(--primary)' }} />
            <div className="text-[15px] font-semibold" style={{ color: 'var(--text-strong)' }}>
              {mods.length === 0 ? '尚未扫描本地 Mod 目录' : '没有匹配的 Mod 记录'}
            </div>
            <p className="max-w-md text-[12.5px]" style={{ color: 'var(--text-muted)' }}>
              {modDirs.length > 0
                ? `当前已配置 ${modDirs.length} 个 Mod 来源目录，点击右上角「扫描仓库」增量建立索引。`
                : '请先在「外观与设置」中配置 KK / KKS 游戏根目录或额外 Mod 目录。'}
            </p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            <table className="w-full border-collapse text-left text-[12.5px]">
              <thead>
                <tr
                  className="sticky top-0"
                  style={{
                    backgroundColor: 'var(--surface-alt)',
                    borderBottom: '1px solid var(--border)',
                    color: 'var(--text-muted)',
                  }}
                >
                  <th className="px-4 py-2.5 font-semibold">名称 / 文件</th>
                  <th className="px-4 py-2.5 font-semibold">GUID</th>
                  <th className="px-4 py-2.5 font-semibold">作者</th>
                  <th className="px-4 py-2.5 font-semibold">版本</th>
                  <th className="px-4 py-2.5 text-right font-semibold">大小</th>
                </tr>
              </thead>
              <tbody>
                {filtered.slice(0, 300).map((m) => (
                  <tr key={m.path} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td className="px-4 py-2.5">
                      <div className="font-medium" style={{ color: 'var(--text-strong)' }}>
                        {m.name || m.fileName}
                      </div>
                      <div className="font-mono-num text-[11px]" style={{ color: 'var(--text-dim)' }}>
                        {m.fileName}
                      </div>
                    </td>
                    <td className="font-mono-num px-4 py-2.5 text-[11.5px]" style={{ color: 'var(--primary)' }}>
                      {m.guid}
                    </td>
                    <td className="px-4 py-2.5" style={{ color: 'var(--text)' }}>
                      {m.author || '-'}
                    </td>
                    <td className="font-mono-num px-4 py-2.5" style={{ color: 'var(--text-muted)' }}>
                      {m.version || '-'}
                    </td>
                    <td className="font-mono-num px-4 py-2.5 text-right" style={{ color: 'var(--text-muted)' }}>
                      {m.sizeMB.toFixed(2)} MB
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

/* ---- 4. 场景卡工具页（完整接通解析 + 一键无损提取角色） ---- */
export const ScenePage: React.FC<{
  scene: SceneAnalysisResult | null
  analyzing: boolean
  extracting: boolean
  onPickScene: () => void
  onExtractCharacters: () => void
}> = ({ scene, analyzing, extracting, onPickScene, onExtractCharacters }) => {
  return (
    <div className="flex h-full flex-col gap-4 overflow-hidden px-5 py-4">
      <div className="kk-surface flex shrink-0 flex-wrap items-center justify-between gap-2 p-4">
        <div>
          <div className="text-[14px] font-bold" style={{ color: 'var(--text-strong)' }}>
            Studio 场景卡解析与角色提取
          </div>
          <div className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
            解析场景卡内嵌的所有角色卡与引用 Mod 清单，支持无损分离提取为独立 PNG
          </div>
        </div>
        <div className="flex items-center gap-2">
          {scene && scene.characterCount > 0 && (
            <button
              type="button"
              disabled={extracting}
              onClick={onExtractCharacters}
              className="kk-btn"
            >
              <Download size={14} />
              <span>{extracting ? '提取中…' : `一键提取全部角色 (${scene.characterCount})`}</span>
            </button>
          )}
          <button
            type="button"
            disabled={analyzing}
            onClick={onPickScene}
            className="kk-btn kk-btn-primary"
          >
            <Clapperboard size={14} />
            <span>{analyzing ? '解析中…' : '选择场景卡 PNG'}</span>
          </button>
        </div>
      </div>

      {!scene ? (
        <div className="kk-surface flex flex-1 flex-col items-center justify-center gap-3 p-10 text-center">
          <Sparkles size={26} style={{ color: 'var(--primary)' }} />
          <div className="text-[15px] font-semibold" style={{ color: 'var(--text-strong)' }}>
            选择一张恋活 Studio 场景卡开始分析
          </div>
          <p className="max-w-sm text-[12.5px]" style={{ color: 'var(--text-muted)' }}>
            直接调用本地 <code className="font-mono-num">core.scene_card.analyze_scene</code> 提取内嵌角色与 Mod GUID。
          </p>
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-hidden lg:grid-cols-[360px_1fr]">
          <div className="kk-surface flex flex-col gap-3 p-4">
            {scene.previewUrl && (
              <img
                src={scene.previewUrl}
                alt={scene.fileName}
                className="w-full rounded-[var(--radius-md)] object-cover"
              />
            )}
            <div className="text-[13.5px] font-semibold" style={{ color: 'var(--text-strong)' }}>
              {scene.fileName}
            </div>
            <div className="font-mono-num text-[12px]" style={{ color: 'var(--text-muted)' }}>
              内嵌角色：{scene.characterCount} 名 · 引用 Mod：{scene.modIds.length} 项
            </div>
          </div>

          <div className="kk-surface flex flex-col gap-3 overflow-y-auto p-4">
            <h3 className="text-[14px] font-semibold" style={{ color: 'var(--text-strong)' }}>
              内嵌角色 ({scene.characters.length})
            </h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {scene.characters.map((ch) => (
                <div key={ch.index} className="kk-surface-alt overflow-hidden">
                  {ch.previewUrl && (
                    <img
                      src={ch.previewUrl}
                      alt={ch.name}
                      className="w-full object-cover"
                      style={{ aspectRatio: '5 / 7' }}
                    />
                  )}
                  <div className="p-2 text-[12.5px] font-medium" style={{ color: 'var(--text-strong)' }}>
                    {ch.name || `角色 #${ch.index + 1}`}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ---- 5. 运行日志页 ---- */
export const LogPage: React.FC<{
  logs: LogEntry[]
  onClear: () => void
}> = ({ logs, onClear }) => {
  return (
    <div className="flex h-full flex-col gap-3.5 overflow-hidden px-5 py-4">
      <div className="kk-surface flex shrink-0 items-center justify-between px-4 py-3">
        <span className="text-[13px] font-semibold" style={{ color: 'var(--text-strong)' }}>
          实时操作记录（共 {logs.length} 条）
        </span>
        <div className="flex gap-2">
        <button type="button" onClick={() => void backend.openLogDirectory()} className="kk-btn text-[12px]">
          <FolderOpen size={13} /><span>打开日志目录</span>
        </button>
        <button type="button" onClick={onClear} className="kk-btn text-[12px]">
          <Trash2 size={13} />
          <span>清空视图</span>
        </button>
        </div>
      </div>

      <div className="kk-surface flex-1 overflow-y-auto p-4">
        <div className="flex flex-col gap-1.5 font-mono-num text-[12px]">
          {logs.map((entry) => (
            <div key={entry.id} className="kk-surface-alt flex items-start gap-3 px-3 py-2">
              <span className="shrink-0" style={{ color: 'var(--text-dim)' }}>
                {entry.time}
              </span>
              <span
                className="w-12 shrink-0 font-semibold uppercase"
                style={{
                  color:
                    entry.level === 'error'
                      ? 'var(--danger)'
                      : entry.level === 'ok'
                        ? 'var(--success)'
                        : entry.level === 'warn'
                          ? 'var(--warning)'
                          : 'var(--primary)',
                }}
              >
                {entry.level}
              </span>
              <span className="shrink-0" style={{ color: 'var(--text-muted)' }}>
                [{entry.source}]
              </span>
              <span className="min-w-0 flex-1 break-all" style={{ color: 'var(--text-strong)' }}>
                {entry.message}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
