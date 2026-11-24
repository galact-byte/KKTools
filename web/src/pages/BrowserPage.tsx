import React, { useMemo, useState } from 'react'
import {
  Clapperboard,
  Edit3,
  ExternalLink,
  FolderOpen,
  FolderSearch,
  Grid2x2,
  Grid3x3,
  LayoutGrid,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from 'lucide-react'
import { CardTagEditor, DataExportButton } from '../components/WorkflowTools'
import { TYPE_META } from '../data/constants'
import type { CardSummary, CardType, LogEntry } from '../types/kk'

interface BrowserPageProps {
  cards: CardSummary[]
  browseDir: string
  quickDirs: Array<{ game: string; label: string; path: string }>
  recursive: boolean
  scanning: boolean
  isDemoMode: boolean
  onChangeBrowseDir: (dir: string) => void
  onSelectQuickDir: (dir: string) => void
  onToggleRecursive: () => void
  onPickDirectory: () => void
  onScan: () => void
  onLoadDemo: () => void
  onQuickEditCard: (card: CardSummary) => void
  onInspectScene: (card: CardSummary) => void
  onTagsSaved: (path: string, tags: string[]) => void
  onRevealFile: (path: string) => void
  onNotify?: (msg: string, tone?: 'info' | 'ok' | 'warn' | 'error') => void
  onLog?: (level: LogEntry['level'], source: string, msg: string) => void
}

type GridDensity = 'compact' | 'standard' | 'large'

export const BrowserPage: React.FC<BrowserPageProps> = ({
  cards,
  browseDir,
  quickDirs,
  recursive,
  scanning,
  isDemoMode,
  onChangeBrowseDir,
  onSelectQuickDir,
  onToggleRecursive,
  onPickDirectory,
  onScan,
  onLoadDemo,
  onQuickEditCard,
  onInspectScene,
  onRevealFile,
  onTagsSaved,
  onNotify,
  onLog,
}) => {
  const [typeFilter, setTypeFilter] = useState<'all' | CardType>('all')
  const [gameFilter, setGameFilter] = useState<string>('all')
  const [keyword, setKeyword] = useState('')
  const [density, setDensity] = useState<GridDensity>('standard')
  const [selectedId, setSelectedId] = useState<string | null>(cards[0]?.id ?? null)
  const [lastExportCsv, setLastExportCsv] = useState('')

  // 仅当当前结果同时存在多个有效游戏版本（如 KK + KKS）时才显示版本筛选胶囊
  const gameOptions = useMemo(() => {
    const map = new Map<string, number>()
    for (const item of cards) {
      if (item.game && item.game !== '?') {
        map.set(item.game, (map.get(item.game) ?? 0) + 1)
      }
    }
    if (map.size < 2) return []
    const order = ['KK', 'KKS', 'EC']
    return Array.from(map.entries()).sort((a, b) => {
      const ia = order.indexOf(a[0])
      const ib = order.indexOf(b[0])
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
    })
  }, [cards])

  const effectiveGameFilter =
    gameFilter !== 'all' && gameOptions.some(([g]) => g === gameFilter) ? gameFilter : 'all'

  const counts = useMemo(() => {
    const c: Record<'all' | CardType, number> = {
      all: 0,
      character: 0,
      coordinate: 0,
      scene: 0,
      other: 0,
    }
    for (const item of cards) {
      if (effectiveGameFilter !== 'all' && item.game !== effectiveGameFilter) continue
      c.all += 1
      c[item.type] = (c[item.type] ?? 0) + 1
    }
    return c
  }, [cards, effectiveGameFilter])

  const filtered = useMemo(() => {
    const q = keyword.trim().toLowerCase()
    return cards.filter((card) => {
      if (effectiveGameFilter !== 'all' && card.game !== effectiveGameFilter) return false
      if (typeFilter !== 'all' && card.type !== typeFilter) return false
      if (!q) return true
      return (
        card.name.toLowerCase().includes(q) ||
        card.fileName.toLowerCase().includes(q) ||
        card.game.toLowerCase().includes(q) ||
        (card.personalityLabel ?? '').toLowerCase().includes(q) ||
        (card.tags || []).some(t => t.toLowerCase().includes(q))
      )
    })
  }, [cards, effectiveGameFilter, typeFilter, keyword])

  const selectedCard = useMemo(
    () => filtered.find((c) => c.id === selectedId) ?? cards.find((c) => c.id === selectedId) ?? null,
    [filtered, cards, selectedId],
  )

  const gridColsClass =
    density === 'compact'
      ? 'grid-cols-3 sm:grid-cols-4 md:grid-cols-5 xl:grid-cols-6'
      : density === 'large'
        ? 'grid-cols-2 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4'
        : 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5'

  const toneBadgeStyle = (type: CardType) => {
    const tone = TYPE_META[type].tone
    if (tone === 'primary') {
      return { backgroundColor: 'var(--primary-soft)', color: 'var(--primary)' }
    }
    if (tone === 'sakura') {
      return { backgroundColor: 'var(--sakura-soft)', color: 'var(--sakura)' }
    }
    if (tone === 'success') {
      return { backgroundColor: 'var(--success-soft)', color: 'var(--success)' }
    }
    return { backgroundColor: 'var(--surface-alt)', color: 'var(--text-muted)' }
  }

  return (
    <div className="flex h-full flex-col gap-3.5 overflow-hidden px-5 py-4">
      {/* 顶部目录与筛选控制条 */}
      <div className="kk-surface flex shrink-0 flex-col gap-3 p-3.5">
        {/* 第一行：目录选择与扫描 */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex min-w-[260px] flex-1 items-center">
            <FolderOpen
              size={15}
              className="pointer-events-none absolute left-3"
              style={{ color: 'var(--text-dim)' }}
            />
            <input
              type="text"
              value={browseDir}
              onChange={(e) => onChangeBrowseDir(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') onScan()
              }}
              placeholder="选择恋活 UserData/chara 或任意角色卡目录..."
              className="kk-input pl-9 pr-3"
            />
          </div>

          <button type="button" onClick={onPickDirectory} className="kk-btn">
            <FolderSearch size={14} />
            <span>选择目录</span>
          </button>

          <label className="flex cursor-pointer items-center gap-1.5 px-2 text-[12.5px]" style={{ color: 'var(--text-muted)' }}>
            <input
              type="checkbox"
              checked={recursive}
              onChange={onToggleRecursive}
              className="h-3.5 w-3.5 accent-[var(--primary)]"
            />
            <span>含子目录</span>
          </label>

          <button
            type="button"
            onClick={onScan}
            disabled={scanning || !browseDir.trim()}
            className="kk-btn kk-btn-primary"
          >
            <RefreshCw size={14} className={scanning ? 'animate-spin' : ''} />
            <span>{scanning ? '扫描中…' : '扫描目录'}</span>
          </button>

          {/* 已在设置中配置 KK / KKS 游戏目录时，自动出现快捷切换胶囊 */}
          {quickDirs.length > 0 && (
            <div className="flex items-center gap-1.5 pl-1">
              {quickDirs.map((qd) => {
                const isCurrent = browseDir.trim().toLowerCase() === qd.path.toLowerCase()
                return (
                  <button
                    key={qd.path}
                    type="button"
                    disabled={scanning}
                    onClick={() => onSelectQuickDir(qd.path)}
                    title={qd.path}
                    className="inline-flex h-8 items-center gap-1 rounded-[var(--radius-sm)] px-2.5 text-[12px] font-medium transition-colors cursor-pointer"
                    style={{
                      backgroundColor: isCurrent ? 'var(--primary-soft)' : 'var(--surface-alt)',
                      border: `1px solid ${isCurrent ? 'var(--primary-border)' : 'var(--border)'}`,
                      color: isCurrent ? 'var(--primary)' : 'var(--text)',
                    }}
                  >
                    <FolderOpen size={12} />
                    <span>{qd.label}</span>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* 第二行：分类胶囊 + 按需版本筛选 + 搜索 + 密度 */}
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex flex-wrap items-center gap-1.5">
            {(['all', 'character', 'coordinate', 'scene', 'other'] as const).map((key) => {
              const active = typeFilter === key
              const label = key === 'all' ? '全部' : TYPE_META[key].label
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setTypeFilter(key)}
                  className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12.5px] font-medium transition-colors cursor-pointer"
                  style={{
                    backgroundColor: active ? 'var(--primary)' : 'var(--surface-alt)',
                    color: active ? 'var(--on-primary)' : 'var(--text)',
                    border: `1px solid ${active ? 'var(--primary)' : 'var(--border)'}`,
                  }}
                >
                  <span>{label}</span>
                  <span
                    className="font-mono-num text-[11px]"
                    style={{ opacity: active ? 0.9 : 0.7 }}
                  >
                    {counts[key]}
                  </span>
                </button>
              )
            })}

            {/* 混放多版本卡片时自动浮现的版本分段胶囊 */}
            {gameOptions.length >= 2 && (
              <div
                className="ml-1 inline-flex items-center rounded-full p-0.5"
                style={{
                  backgroundColor: 'var(--surface-alt)',
                  border: '1px solid var(--border)',
                }}
              >
                <button
                  type="button"
                  onClick={() => setGameFilter('all')}
                  className="rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold transition-colors cursor-pointer"
                  style={{
                    backgroundColor: effectiveGameFilter === 'all' ? 'var(--surface)' : 'transparent',
                    color: effectiveGameFilter === 'all' ? 'var(--primary)' : 'var(--text-muted)',
                  }}
                >
                  全版本
                </button>
                {gameOptions.map(([gameTag, cnt]) => {
                  const active = effectiveGameFilter === gameTag
                  return (
                    <button
                      key={gameTag}
                      type="button"
                      onClick={() => setGameFilter(gameTag)}
                      className="font-mono-num inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold transition-colors cursor-pointer"
                      style={{
                        backgroundColor: active ? 'var(--surface)' : 'transparent',
                        color: active ? 'var(--primary)' : 'var(--text-muted)',
                      }}
                    >
                      <span>{gameTag}</span>
                      <span className="text-[10.5px]" style={{ opacity: 0.72 }}>
                        {cnt}
                      </span>
                    </button>
                  )
                })}
              </div>
            )}

            {isDemoMode && (
              <span
                title="画廊示范样例，可直接点选试玩编辑；选择本地目录后切换为你的真实角色卡"
                className="ml-1 inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11.5px] font-medium"
                style={{
                  backgroundColor: 'var(--sakura-soft)',
                  color: 'var(--sakura)',
                  border: '1px solid var(--sakura-border)',
                }}
              >
                <Sparkles size={12} />
                <span>示范样例</span>
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* 搜索框 */}
            <div className="relative w-44">
              <Search
                size={14}
                className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2"
                style={{ color: 'var(--text-dim)' }}
              />
              <input
                type="text"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="名称 / 文件名 / 标签"
                className="kk-input h-8 py-1 pl-8 pr-7 text-[12px]"
              />
              {keyword && (
                <button
                  type="button"
                  onClick={() => setKeyword('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 cursor-pointer"
                  style={{ color: 'var(--text-dim)' }}
                  aria-label="清空搜索"
                >
                  <X size={13} />
                </button>
              )}
            </div>

            {!isDemoMode && filtered.some((c) => !c.isDemo) && (
              <div className="flex items-center gap-1">
                <DataExportButton
                  kind="list"
                  paths={filtered.filter((c) => !c.isDemo).map((c) => c.path)}
                  format="csv"
                  label="导出 CSV"
                  title="导出当前筛选结果列表为 CSV"
                  className="kk-btn h-8 shrink-0 px-2 text-[12px]"
                  onExported={setLastExportCsv}
                  onNotify={onNotify}
                  onLog={onLog}
                />
                {lastExportCsv && (
                  <button
                    type="button"
                    onClick={() => onRevealFile(lastExportCsv)}
                    title={`在资源管理器中定位：${lastExportCsv}`}
                    aria-label="在资源管理器中定位导出的 CSV"
                    className="kk-btn h-8 shrink-0 px-2 text-[12px]"
                  >
                    <ExternalLink size={13} />
                  </button>
                )}
              </div>
            )}

            {/* 网格密度 */}
            <div
              className="flex items-center rounded-[var(--radius-sm)] p-0.5"
              style={{ backgroundColor: 'var(--surface-alt)', border: '1px solid var(--border)' }}
            >
              {(
                [
                  { id: 'compact', icon: Grid3x3, title: '紧凑网格' },
                  { id: 'standard', icon: LayoutGrid, title: '标准画廊' },
                  { id: 'large', icon: Grid2x2, title: '大立绘展示' },
                ] as const
              ).map(({ id, icon: Icon, title }) => {
                const active = density === id
                return (
                  <button
                    key={id}
                    type="button"
                    title={title}
                    aria-label={title}
                    onClick={() => setDensity(id)}
                    className="flex h-7 w-7 items-center justify-center rounded-[6px] transition-colors cursor-pointer"
                    style={{
                      backgroundColor: active ? 'var(--surface)' : 'transparent',
                      color: active ? 'var(--primary)' : 'var(--text-muted)',
                    }}
                  >
                    <Icon size={14} />
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      {/* 主体：左画廊网格 + 右玻璃检视抽屉 */}
      <div className="flex min-h-0 flex-1 gap-4 overflow-hidden">
        {/* 画廊网格区 */}
        <div className="flex-1 overflow-y-auto pr-1">
          {filtered.length === 0 ? (
            <div className="kk-surface flex h-full flex-col items-center justify-center gap-3 p-10 text-center">
              <div
                className="flex h-12 w-12 items-center justify-center rounded-full"
                style={{ backgroundColor: 'var(--primary-soft)', color: 'var(--primary)' }}
              >
                <FolderSearch size={22} />
              </div>
              <div className="text-[15px] font-semibold" style={{ color: 'var(--text-strong)' }}>
                {cards.length === 0 ? '还没有扫描到角色卡' : '没有符合当前筛选条件的卡片'}
              </div>
              <p className="max-w-sm text-[13px]" style={{ color: 'var(--text-muted)' }}>
                选择你的恋活 UserData 目录扫描本地角色卡，或者先载入内置示范画廊体验全新界面。
              </p>
              <div className="mt-1 flex items-center gap-2.5">
                <button type="button" onClick={onPickDirectory} className="kk-btn kk-btn-primary">
                  <FolderOpen size={14} />
                  <span>选择本地角色卡目录</span>
                </button>
                <button type="button" onClick={onLoadDemo} className="kk-btn">
                  <Sparkles size={14} />
                  <span>查看示范画廊</span>
                </button>
              </div>
            </div>
          ) : (
            <div className={`grid gap-3.5 pb-4 ${gridColsClass}`}>
              {filtered.map((card) => {
                const selected = selectedCard?.id === card.id
                return (
                  <div
                    key={card.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedId(card.id)}
                    onDoubleClick={() => {
                      if (card.type === 'character') onQuickEditCard(card)
                      else if (card.type === 'scene') onInspectScene(card)
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setSelectedId(card.id)
                      }
                    }}
                    className="kk-surface group relative flex flex-col overflow-hidden text-left transition-all cursor-pointer"
                    style={{
                      borderColor: selected ? 'var(--primary)' : undefined,
                      boxShadow: selected
                        ? '0 0 0 2px var(--primary-soft), var(--shadow-float)'
                        : undefined,
                    }}
                  >
                    {/* 5:7 恋活立绘主视窗 */}
                    <div
                      className="relative w-full overflow-hidden"
                      style={{ aspectRatio: '5 / 7', backgroundColor: 'var(--surface-alt)' }}
                    >
                      <img
                        src={card.thumbnailUrl}
                        alt={card.name || card.fileName}
                        loading="lazy"
                        className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
                      />

                      {/* 顶部玻璃角标：游戏代号 + 类型 */}
                      <div className="pointer-events-none absolute left-2 top-2 flex items-center gap-1">
                        {card.game && card.game !== '?' && (
                          <span
                            className="font-mono-num rounded-[6px] px-1.5 py-0.5 text-[10.5px] font-bold tracking-wider backdrop-blur-md"
                            style={{
                              backgroundColor: 'rgba(15, 25, 45, 0.68)',
                              color: '#ffffff',
                            }}
                          >
                            {card.game}
                          </span>
                        )}
                      </div>

                      {/* 悬浮快捷按钮：角色卡原地弹窗编辑，场景卡直达场景解析 */}
                      {card.type === 'character' && (
                        <div className="absolute right-2 bottom-2 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              onQuickEditCard(card)
                            }}
                            className="inline-flex items-center gap-1 rounded-[8px] px-2.5 py-1 text-[11.5px] font-semibold shadow-sm backdrop-blur-md cursor-pointer"
                            style={{
                              backgroundColor: 'var(--primary)',
                              color: 'var(--on-primary)',
                            }}
                          >
                            <Edit3 size={12} />
                            <span>编辑</span>
                          </button>
                        </div>
                      )}
                      {card.type === 'scene' && (
                        <div className="absolute right-2 bottom-2 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              onInspectScene(card)
                            }}
                            className="inline-flex items-center gap-1 rounded-[8px] px-2.5 py-1 text-[11.5px] font-semibold shadow-sm backdrop-blur-md cursor-pointer"
                            style={{
                              backgroundColor: 'var(--success)',
                              color: '#ffffff',
                            }}
                          >
                            <Clapperboard size={12} />
                            <span>解析场景</span>
                          </button>
                        </div>
                      )}
                    </div>

                    {/* 底部纯净档案签 */}
                    <div className="flex flex-col gap-1 px-3 py-2.5">
                      <div className="flex items-center justify-between gap-1.5">
                        <span
                          className="truncate text-[13.5px] font-semibold"
                          style={{ color: 'var(--text-strong)' }}
                        >
                          {card.name || card.fileName.replace(/\.png$/i, '')}
                        </span>
                        <span
                          className="shrink-0 rounded-[5px] px-1.5 py-[1px] text-[10.5px] font-medium"
                          style={toneBadgeStyle(card.type)}
                        >
                          {TYPE_META[card.type].label}
                        </span>
                      </div>
                      <div
                        className="flex items-center justify-between text-[11.5px]"
                        style={{ color: 'var(--text-dim)' }}
                      >
                        <span className="truncate">{card.subtitle || card.fileName}</span>
                        {card.personalityLabel && card.type === 'character' && (
                          <span className="shrink-0 pl-1" style={{ color: 'var(--sakura)' }}>
                            {card.personalityLabel}
                          </span>
                        )}
                      </div>
                      {card.tags && card.tags.length > 0 && (
                        <div className="mt-0.5 flex flex-nowrap items-center gap-1 overflow-hidden">
                          {(card.tags.length > 2 ? card.tags.slice(0, 1) : card.tags).map((tag) => (
                            <span
                              key={tag}
                              className="min-w-0 truncate rounded-full px-1.5 py-[1px] text-[10px] font-medium"
                              style={{
                                backgroundColor: 'var(--primary-soft)',
                                color: 'var(--primary)',
                              }}
                            >
                              #{tag}
                            </span>
                          ))}
                          {card.tags.length > 2 && (
                            <span
                              className="font-mono-num shrink-0 rounded-full px-1.5 py-[1px] text-[10px]"
                              style={{
                                backgroundColor: 'var(--surface-alt)',
                                color: 'var(--text-dim)',
                              }}
                            >
                              +{card.tags.length - 1}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* 右侧玻璃检视面板（Inspector） */}
        {selectedCard && (
          <aside
            key={selectedCard.id}
            className="kk-surface kk-drawer-enter flex w-[308px] shrink-0 flex-col overflow-hidden"
          >
            <div
              className="flex items-center justify-between px-4 py-3"
              style={{ borderBottom: '1px solid var(--border)' }}
            >
              <div className="flex items-center gap-2">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: 'var(--primary)' }}
                />
                <span className="text-[13px] font-semibold" style={{ color: 'var(--text-strong)' }}>
                  卡片档案预览
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedId(null)}
                className="kk-btn-ghost flex h-6 w-6 items-center justify-center rounded-[6px] cursor-pointer"
                aria-label="收起预览"
              >
                <X size={14} />
              </button>
            </div>

            <div className="flex flex-1 flex-col gap-3.5 overflow-y-auto p-4">
              {/* 高清完整立绘框 */}
              <div
                className="mx-auto w-[216px] shrink-0 overflow-hidden rounded-[var(--radius-md)] border"
                style={{
                  aspectRatio: '5 / 7',
                  borderColor: 'var(--border)',
                  backgroundColor: 'var(--surface-alt)',
                }}
              >
                <img
                  src={selectedCard.thumbnailUrl}
                  alt={selectedCard.name || selectedCard.fileName}
                  className="h-full w-full object-cover"
                />
              </div>

              {/* 角色标题与徽章 */}
              <div>
                <div className="flex items-center gap-2">
                  <h2
                    className="font-display truncate text-[18px] font-bold"
                    style={{ color: 'var(--text-strong)' }}
                  >
                    {selectedCard.name || selectedCard.fileName.replace(/\.png$/i, '')}
                  </h2>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  <span
                    className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
                    style={toneBadgeStyle(selectedCard.type)}
                  >
                    {TYPE_META[selectedCard.type].label}
                  </span>
                  {selectedCard.game && selectedCard.game !== '?' && (
                    <span
                      className="font-mono-num rounded-full px-2 py-0.5 text-[11px] font-semibold"
                      style={{ backgroundColor: 'var(--surface-alt)', color: 'var(--text)' }}
                    >
                      {selectedCard.game}
                    </span>
                  )}
                  {selectedCard.personalityLabel && (
                    <span
                      className="rounded-full px-2 py-0.5 text-[11px] font-medium"
                      style={{ backgroundColor: 'var(--sakura-soft)', color: 'var(--sakura)' }}
                    >
                      {selectedCard.personalityLabel}
                    </span>
                  )}
                </div>
              </div>

              {/* 关键信息表 */}
              <div className="kk-surface-alt flex flex-col gap-2 p-3 text-[12px]">
                <div className="flex items-center justify-between gap-2">
                  <span style={{ color: 'var(--text-dim)' }}>文件名</span>
                  <span
                    className="font-mono-num truncate font-medium"
                    style={{ color: 'var(--text-strong)' }}
                    title={selectedCard.fileName}
                  >
                    {selectedCard.fileName}
                  </span>
                </div>
                {selectedCard.birthday && (
                  <div className="flex items-center justify-between gap-2">
                    <span style={{ color: 'var(--text-dim)' }}>生日 / 血型</span>
                    <span className="font-mono-num font-medium" style={{ color: 'var(--text)' }}>
                      {selectedCard.birthday} · {selectedCard.bloodType || '-'}型
                    </span>
                  </div>
                )}
                {typeof selectedCard.modCount === 'number' && (
                  <div className="flex items-center justify-between gap-2">
                    <span style={{ color: 'var(--text-dim)' }}>引用 Mod</span>
                    <span className="font-mono-num font-medium" style={{ color: 'var(--text)' }}>
                      {selectedCard.modCount} 项
                    </span>
                  </div>
                )}
                <div className="flex flex-col gap-0.5 pt-1" style={{ borderTop: '1px solid var(--border)' }}>
                  <span style={{ color: 'var(--text-dim)' }}>来源路径</span>
                  <span
                    className="font-mono-num break-all text-[11px]"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    {selectedCard.path}
                  </span>
                </div>
              </div>

              {!selectedCard.isDemo && (
                <CardTagEditor
                  key={selectedCard.path}
                  path={selectedCard.path}
                  onSaved={(tags) => onTagsSaved(selectedCard.path, tags)}
                  onNotify={onNotify}
                  onLog={onLog}
                />
              )}
            </div>

            {/* 底部操作区 */}
            <div
              className="flex flex-col gap-2 p-3.5"
              style={{ borderTop: '1px solid var(--border)' }}
            >
              {selectedCard.type === 'character' && (
                <button
                  type="button"
                  onClick={() => onQuickEditCard(selectedCard)}
                  className="kk-btn kk-btn-primary w-full py-2"
                >
                  <Edit3 size={14} />
                  <span>弹窗快速编辑</span>
                </button>
              )}
              {selectedCard.type === 'scene' && (
                <button
                  type="button"
                  onClick={() => onInspectScene(selectedCard)}
                  className="kk-btn kk-btn-primary w-full py-2"
                >
                  <Clapperboard size={14} />
                  <span>解析场景卡</span>
                </button>
              )}
              {!selectedCard.isDemo && (
                <button
                  type="button"
                  onClick={() => onRevealFile(selectedCard.path)}
                  className="kk-btn w-full py-1.5 text-[12px]"
                >
                  <ExternalLink size={13} />
                  <span>在资源管理器中定位</span>
                </button>
              )}
            </div>
          </aside>
        )}
      </div>
    </div>
  )
}
