import React, { useState } from 'react'
import { backend, waitTask } from '../lib/bridge'

export const ModExchange: React.FC<{ notify: (text: string, tone?: 'info' | 'ok' | 'warn' | 'error') => void }> = ({ notify }) => {
  const [busy, setBusy] = useState(false)
  const [summary, setSummary] = useState('')
  const run = async (action: 'export' | 'compare' | 'fill') => {
    if (busy) return
    setBusy(true)
    try {
      if (action === 'export') {
        const pick = await backend.pickSaveTxt('保存本机 Mod 清单（JSON 内容）')
        if (!pick.ok || !pick.data) return
        const result = await backend.exportManifest(pick.data)
        if (!result.ok) throw new Error(result.error)
        notify(`已导出 ${result.data?.count ?? 0} 项 Mod 清单`, 'ok')
      } else {
        const pick = await backend.pickAnyFiles('选择对方清单（JSON 或每行一个 GUID 的文本）', false)
        if (!pick.ok || typeof pick.data !== 'string' || !pick.data) return
        if (action === 'compare') {
          const result = await backend.compareManifest(pick.data)
          if (!result.ok || !result.data) throw new Error(result.error)
          const r = result.data
          setSummary(`双方共有 ${r.both} 项；我可补给对方 ${r.mine_only.length} 项；对方可补给我 ${r.theirs_only.length} 项。\n我缺少的 GUID：\n${r.theirs_only.join('\n') || '无'}`)
        } else {
          const output = await backend.pickDirectory('选择 Mod 压缩包输出目录')
          if (!output.ok || !output.data) return
          const start = await backend.startExportModList(pick.data, output.data)
          if (!start.ok || !start.data) throw new Error(start.error)
          const result = await waitTask<{ count: number; path: string }>(start.data.taskId)
          if (!result.ok || !result.data) throw new Error(result.error)
          notify(`已导出 ${result.data.count} 个 Mod：${result.data.path}`, 'ok')
        }
      }
    } catch (err) {
      notify(err instanceof Error ? err.message : String(err), 'error')
    } finally { setBusy(false) }
  }
  return <section className="kk-surface flex flex-col gap-3 p-4">
    <div className="text-[13px] font-semibold">清单互助</div>
    <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>导出本机清单，与对方清单比较，或按收到的缺失清单打包本机已有的 Mod。</p>
    <div className="flex flex-wrap gap-2">
      <button type="button" disabled={busy} className="kk-btn" onClick={() => void run('export')}>导出本机清单</button>
      <button type="button" disabled={busy} className="kk-btn" onClick={() => void run('compare')}>导入对方清单并对账</button>
      <button type="button" disabled={busy} className="kk-btn" onClick={() => void run('fill')}>按缺失清单导出 Mod 包</button>
    </div>
    {summary && <pre className="max-h-40 overflow-auto whitespace-pre-wrap text-[12px] select-text">{summary}</pre>}
  </section>
}
