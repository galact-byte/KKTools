import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Clapperboard,
  Edit3,
  ExternalLink,
  FolderOpen,
  FolderSearch,
  Grid2x2,
  Grid3x3,
  LayoutGrid,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  UserRound,
  Users,
  X,
} from 'lucide-react'
import {
  AUTHOR_SOURCE_LABEL,
  CardAuthorEditor,
  CardTagEditor,
  ConvertCardButton,
  DataExportButton,
} from '../components/WorkflowTools'
import { TYPE_META } from '../data/constants'
import { backend } from '../lib/bridge'
import {
  allocateAuthorRenderBudget,
  formatCardTypeBadge,
  normalizeDisplayAuthor,
  normalizeUserId,
} from '../lib/cardDisplay'
import type { AuthorSource, CardPageQueryOptions, CardSummary, CardType, LogEntry } from '../types/kk'

export interface BrowserFilterState {
  type: 'all' | CardType
  game: string
  author: string
  search: string
}

export interface BrowserPageMeta {
  total: number
  hasMore: boolean
  indexed: boolean
  complete: boolean
  versionCounts: Array<[string, number]>
}

interface BrowserPageProps {
  cards: CardSummary[]
  browseDir: string
  scannedDir: string
  quickDirs: Array<{ game: string; label: string; path: string }>
  recursive: boolean
  scanning: boolean
  scanProgress?: { percent: number; message: string } | null
  loadingPage: boolean
  pageMeta: BrowserPageMeta
  filters: BrowserFilterState
  isDemoMode: boolean
  onChangeBrowseDir: (dir: string) => void
  onSelectQuickDir: (dir: string) => void
  onToggleRecursive: () => void
  onChangeFilters: (next: BrowserFilterState) => void
  onLoadMore: () => void
  onPickDirectory: () => void
  onScan: () => void
  onCancelScan?: () => void
  onLoadDemo: () => void
  onQuickEditCard: (card: CardSummary) => void
  onInspectScene: (card: CardSummary) => void
  onTagsSaved: (path: string, tags: string[]) => void
  onAuthorSaved: (path: string, author: string, source: AuthorSource, history: string[]) => void
  onCardConverted?: (savedPath: string, targetGame: 'KK' | 'KKS') => void
  onRevealFile: (path: string) => void
  onNotify?: (msg: string, tone?: 'info' | 'ok' | 'warn' | 'error') => void
  onLog?: (level: LogEntry['level'], source: string, msg: string) => void
}

type GridDensity = 'compact' | 'standard' | 'large'
type ViewMode = 'grid' | 'author'

interface AuthorGroupPageState {
  items: CardSummary[]
  total: number
  hasMore: boolean
  loading: boolean
  loadedFromIndex: boolean
}

const PAGE_BATCH_SIZE = 120
const GROUP_INITIAL_LIMIT = 40
const UNKNOWN_AUTHOR_KEY = '__UNKNOWN__'

export const BrowserPage: React.FC<BrowserPageProps> = ({
  cards,
  browseDir,
  scannedDir,
  quickDirs,
  recursive,
  scanning,
  scanProgress,
  loadingPage,
  pageMeta,
  filters,
  isDemoMode,
  onChangeBrowseDir,
  onSelectQuickDir,
  onToggleRecursive,
  onChangeFilters,
  onLoadMore,
  onPickDirectory,
  onScan,
  onCancelScan,
  onLoadDemo,
  onQuickEditCard,
  onInspectScene,
  onRevealFile,
  onTagsSaved,
  onAuthorSaved,
  onCardConverted,
  onNotify,
  onLog,
}) => {
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [searchInput, setSearchInput] = useState(filters.search)
  const [density, setDensity] = useState<GridDensity>('standard')
  const [selectedId, setSelectedId] = useState<string | null>(cards[0]?.id ?? null)
  const [lastExportCsv, setLastExportCsv] = useState('')
  const [demoVisibleCount, setDemoVisibleCount] = useState(PAGE_BATCH_SIZE)
  const [authorRenderBudget, setAuthorRenderBudget] = useState(PAGE_BATCH_SIZE)
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({})
  const [groupLimits, setGroupLimits] = useState<Record<string, number>>({})
  const [authorGroupPages, setAuthorGroupPages] = useState<Record<string, AuthorGroupPageState>>({})
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const groupQueryVersionRef = useRef(0)
  const authorScope = JSON.stringify([isDemoMode, scannedDir, recursive])
  const [knownAuthors, setKnownAuthors] = useState<{ scope: string; names: string[] }>({
    scope: authorScope,
    names: [],
  })
  const hasUnfilteredResults =
    filters.type === 'all' && filters.game === 'all' &&
    filters.author === 'all' && !filters.search.trim()
  const authorCountsComplete = isDemoMode ||
    (hasUnfilteredResults && pageMeta.indexed && !pageMeta.hasMore)

  // 候选独立于作者/搜索筛选保留；切换目录或递归范围后重新收集。
  useEffect(() => {
    if (isDemoMode || scanning || loadingPage) return
    const names = cards.map((card) => normalizeDisplayAuthor(card.author)).filter(Boolean)
    setKnownAuthors((prev) => {
      const retained = prev.scope === authorScope && !authorCountsComplete ? prev.names : []
      const next = [...new Set([...retained, ...names])]
      if (prev.scope === authorScope && next.length === prev.names.length &&
          next.every((name, i) => name === prev.names[i])) return prev
      return { scope: authorScope, names: next }
    })
  }, [cards, authorScope, isDemoMode, scanning, loadingPage, authorCountsComplete])

  const typeFilter = filters.type
  const gameFilter = filters.game
  const authorFilter = filters.author

  // 外部重置搜索条件（切换目录/递归）时同步输入框
  useEffect(() => {
    setSearchInput(filters.search)
  }, [filters.search])

  // 搜索输入防抖后提交到服务端/本地筛选
  useEffect(() => {
    if (searchInput === filters.search) return
    const delay = searchInput.trim() === '' ? 0 : 220
    const timer = window.setTimeout(() => {
      onChangeFilters({ ...filters, search: searchInput })
    }, delay)
    return () => window.clearTimeout(timer)
  }, [searchInput, filters, onChangeFilters])

  // 目录、递归或筛选变化时重置滚动位置、作者分组缓存与渲染预算
  useEffect(() => {
    groupQueryVersionRef.current += 1
    setDemoVisibleCount(PAGE_BATCH_SIZE)
    setAuthorRenderBudget(PAGE_BATCH_SIZE)
    setCollapsedGroups({})
    setGroupLimits({})
    setAuthorGroupPages({})
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0
    }
  }, [
    isDemoMode,
    scannedDir,
    recursive,
    filters.type,
    filters.game,
    filters.author,
    filters.search,
    viewMode,
  ])

  // 仅当存在多个有效游戏版本（如 KK + KKS）时才显示版本筛选胶囊
  const gameOptions = useMemo(() => {
    if (!isDemoMode) {
      return pageMeta.versionCounts.length >= 2 ? pageMeta.versionCounts : []
    }
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
  }, [isDemoMode, pageMeta.versionCounts, cards])

  const effectiveGameFilter =
    gameFilter !== 'all' && gameOptions.some(([g]) => g === gameFilter) ? gameFilter : 'all'

  // 统计作者下拉选项：演示模式为全量；本地分页模式仅代表已加载卡片中见到的作者
  const authorOptions = useMemo(() => {
    const map = new Map<string, number>()
    let unknownCount = 0
    for (const item of cards) {
      if (isDemoMode && effectiveGameFilter !== 'all' && item.game !== effectiveGameFilter) continue
      const a = normalizeDisplayAuthor(item.author)
      if (a) {
        map.set(a, (map.get(a) ?? 0) + 1)
      } else {
        unknownCount += 1
      }
    }
    if (!isDemoMode && knownAuthors.scope === authorScope) {
      for (const author of knownAuthors.names) {
        if (!map.has(author)) map.set(author, 0)
      }
    }
    if (
      authorFilter !== 'all' &&
      authorFilter !== UNKNOWN_AUTHOR_KEY &&
      !map.has(authorFilter)
    ) {
      map.set(authorFilter, 0)
    }
    const sorted = Array.from(map.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    return { named: sorted, unknownCount }
  }, [cards, isDemoMode, effectiveGameFilter, authorFilter, knownAuthors, authorScope])

  const effectiveAuthorFilter =
    authorFilter === 'all' ||
    authorFilter === UNKNOWN_AUTHOR_KEY ||
    authorOptions.named.some(([a]) => a === authorFilter)
      ? authorFilter
      : 'all'

  // 演示模式下计算各分类数；本地分页模式下不把当前页局部计数冒充全库各分类统计
  const counts = useMemo(() => {
    const c: Record<'all' | CardType, number | null> = {
      all: null,
      character: null,
      coordinate: null,
      scene: null,
      other: null,
    }
    if (isDemoMode || (!pageMeta.hasMore && pageMeta.indexed)) {
      c.all = 0
      c.character = 0
      c.coordinate = 0
      c.scene = 0
      c.other = 0
      for (const item of cards) {
        if (isDemoMode && effectiveGameFilter !== 'all' && item.game !== effectiveGameFilter) continue
        const a = normalizeDisplayAuthor(item.author)
        if (isDemoMode && effectiveAuthorFilter === UNKNOWN_AUTHOR_KEY && a) continue
        if (
          isDemoMode &&
          effectiveAuthorFilter !== 'all' &&
          effectiveAuthorFilter !== UNKNOWN_AUTHOR_KEY &&
          a !== effectiveAuthorFilter
        ) {
          continue
        }
        c.all += 1
        c[item.type] = (c[item.type] ?? 0) + 1
      }
      if (!isDemoMode) {
        c[typeFilter] = pageMeta.total
      }
      return c
    }
    if (pageMeta.indexed) {
      c[typeFilter] = pageMeta.total
    }
    return c
  }, [
    cards,
    isDemoMode,
    effectiveGameFilter,
    effectiveAuthorFilter,
    typeFilter,
    pageMeta.hasMore,
    pageMeta.indexed,
    pageMeta.total,
  ])

  // 演示模式前端过滤；本地库模式严格使用后端 SQLite 分页查询结果，不做二次前端截断过滤
  const filtered = useMemo(() => {
    if (!isDemoMode) return cards
    const q = filters.search.trim().toLowerCase()
    return cards.filter((card) => {
      if (effectiveGameFilter !== 'all' && card.game !== effectiveGameFilter) return false
      if (typeFilter !== 'all' && card.type !== typeFilter) return false
      const cardAuthor = normalizeDisplayAuthor(card.author)
      if (effectiveAuthorFilter === UNKNOWN_AUTHOR_KEY && cardAuthor) return false
      if (
        effectiveAuthorFilter !== 'all' &&
        effectiveAuthorFilter !== UNKNOWN_AUTHOR_KEY &&
        cardAuthor !== effectiveAuthorFilter
      ) {
        return false
      }
      if (!q) return true
      return (
        card.name.toLowerCase().includes(q) ||
        card.fileName.toLowerCase().includes(q) ||
        card.game.toLowerCase().includes(q) ||
        cardAuthor.toLowerCase().includes(q) ||
        (card.personalityLabel ?? '').toLowerCase().includes(q) ||
        (card.tags || []).some((t) => t.toLowerCase().includes(q))
      )
    })
  }, [isDemoMode, cards, effectiveGameFilter, effectiveAuthorFilter, typeFilter, filters.search])

  // 按作者分组数据结构（已知作者按已载入数降序，未知作者沉底）
  const authorGroups = useMemo(() => {
    if (viewMode !== 'author') return []
    const map = new Map<string, CardSummary[]>()
    const unknown: CardSummary[] = []
    for (const card of filtered) {
      const a = normalizeDisplayAuthor(card.author)
      if (!a) {
        unknown.push(card)
      } else {
        const list = map.get(a)
        if (list) list.push(card)
        else map.set(a, [card])
      }
    }
    const groups = Array.from(map.entries())
      .sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]))
      .map(([author, loadedItems]) => {
        const paged = authorGroupPages[author]
        return {
          key: author,
          label: author,
          isUnknown: false,
          items: paged?.loadedFromIndex ? paged.items : loadedItems,
          total: paged?.loadedFromIndex ? paged.total : undefined,
          hasMore: paged?.loadedFromIndex ? paged.hasMore : !isDemoMode && pageMeta.hasMore,
          loading: Boolean(paged?.loading),
          loadedFromIndex: Boolean(paged?.loadedFromIndex),
        }
      })
    if (unknown.length > 0) {
      const paged = authorGroupPages[UNKNOWN_AUTHOR_KEY]
      groups.push({
        key: UNKNOWN_AUTHOR_KEY,
        label: '未知作者',
        isUnknown: true,
        items: paged?.loadedFromIndex ? paged.items : unknown,
        total: paged?.loadedFromIndex ? paged.total : undefined,
        hasMore: paged?.loadedFromIndex ? paged.hasMore : !isDemoMode && pageMeta.hasMore,
        loading: Boolean(paged?.loading),
        loadedFromIndex: Boolean(paged?.loadedFromIndex),
      })
    }
    return groups
  }, [filtered, viewMode, authorGroupPages, isDemoMode, pageMeta.hasMore])

  const exportCards = useMemo(() => {
    const loaded = viewMode === 'author'
      ? [...filtered, ...authorGroups.flatMap((group) => group.items)]
      : filtered
    return [...new Map(loaded.filter((card) => !card.isDemo).map((card) => [card.path, card])).values()]
  }, [viewMode, authorGroups, filtered])

  const authorBudgetPlan = useMemo(
    () =>
      allocateAuthorRenderBudget(authorGroups, {
        totalBudget: authorRenderBudget,
        defaultGroupLimit: GROUP_INITIAL_LIMIT,
        collapsedGroups,
        groupLimits,
      }),
    [authorGroups, authorRenderBudget, collapsedGroups, groupLimits],
  )

  const loadAuthorGroupPage = useCallback(
    async (groupKey: string, isUnknown: boolean, append: boolean) => {
      if (isDemoMode || !scannedDir.trim()) return
      const existing = authorGroupPages[groupKey]
      if (existing?.loading) return
      const version = groupQueryVersionRef.current
      const offset = append && existing?.loadedFromIndex ? existing.items.length : 0

      setAuthorGroupPages((prev) => ({
        ...prev,
        [groupKey]: {
          items: prev[groupKey]?.items ?? [],
          total: prev[groupKey]?.total ?? 0,
          hasMore: prev[groupKey]?.hasMore ?? false,
          loadedFromIndex: prev[groupKey]?.loadedFromIndex ?? false,
          loading: true,
        },
      }))

      const opts: CardPageQueryOptions = {
        recursive,
        offset,
        limit: GROUP_INITIAL_LIMIT,
        author: isUnknown ? '' : groupKey,
      }
      if (filters.type !== 'all') opts.type = filters.type as CardType
      if (filters.game !== 'all') opts.game = filters.game as CardPageQueryOptions['game']
      if (filters.search.trim()) opts.search = filters.search.trim()

      const res = await backend.queryCardPage(scannedDir, opts)
      if (version !== groupQueryVersionRef.current) return

      if (!res.ok || !res.data) {
        setAuthorGroupPages((prev) => {
          const cur = prev[groupKey]
          if (!cur) return prev
          return { ...prev, [groupKey]: { ...cur, loading: false } }
        })
        onNotify?.(`查询作者卡片失败：${res.error || '未知错误'}`, 'error')
        return
      }

      const page = res.data
      let nextItemCount = page.items.length
      setAuthorGroupPages((prev) => {
        const prevItems = append && prev[groupKey]?.loadedFromIndex ? prev[groupKey].items : []
        const seen = new Set(prevItems.map((c) => c.id))
        const merged = [...prevItems]
        for (const item of page.items) {
          if (!seen.has(item.id)) {
            seen.add(item.id)
            merged.push(item)
          }
        }
        nextItemCount = merged.length
        return {
          ...prev,
          [groupKey]: {
            items: merged,
            total: page.total,
            hasMore: page.hasMore,
            loadedFromIndex: true,
            loading: false,
          },
        }
      })
      setGroupLimits((prev) => ({
        ...prev,
        [groupKey]: Math.max(prev[groupKey] ?? GROUP_INITIAL_LIMIT, nextItemCount),
      }))
      if (append) {
        setAuthorRenderBudget((prev) => prev + GROUP_INITIAL_LIMIT)
      }
    },
    [
      isDemoMode,
      scannedDir,
      authorGroupPages,
      recursive,
      filters.type,
      filters.game,
      filters.search,
      onNotify,
    ],
  )

  const selectedCard = useMemo(() => {
    const inFiltered = filtered.find((c) => c.id === selectedId)
    if (inFiltered) return inFiltered
    const inCards = cards.find((c) => c.id === selectedId)
    if (inCards) return inCards
    for (const gp of Object.values(authorGroupPages)) {
      const hit = gp.items.find((c) => c.id === selectedId)
      if (hit) return hit
    }
    return null
  }, [filtered, cards, authorGroupPages, selectedId])

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

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (viewMode !== 'grid') return
    const el = e.currentTarget
    if (el.scrollHeight - el.scrollTop - el.clientHeight >= 360) return
    if (isDemoMode) {
      if (demoVisibleCount < filtered.length) {
        setDemoVisibleCount((prev) => Math.min(filtered.length, prev + PAGE_BATCH_SIZE))
      }
    } else if (pageMeta.hasMore && !loadingPage && !scanning) {
      onLoadMore()
    }
  }

  const renderCardTile = (card: CardSummary) => {
    const selected = selectedCard?.id === card.id
    const displayAuthor = normalizeDisplayAuthor(card.author)
    const badgeText = formatCardTypeBadge(card.type, card.game)
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
          boxShadow: selected ? '0 0 0 2px var(--primary-soft), var(--shadow-float)' : undefined,
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
            decoding="async"
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
          />

          {/* 顶部玻璃角标：游戏代号（服装卡版本未知时显示「版本未知」，不强行归到 KK） */}
          <div className="pointer-events-none absolute left-2 top-2 flex items-center gap-1">
            {card.game && card.game !== '?' ? (
              <span
                className="font-mono-num rounded-[6px] px-1.5 py-0.5 text-[10.5px] font-bold tracking-wider backdrop-blur-md"
                style={{
                  backgroundColor: 'rgba(15, 25, 45, 0.68)',
                  color: '#ffffff',
                }}
              >
                {card.game}
              </span>
            ) : card.type === 'coordinate' ? (
              <span
                className="rounded-[6px] px-1.5 py-0.5 text-[10px] font-medium backdrop-blur-md"
                style={{
                  backgroundColor: 'rgba(15, 25, 45, 0.58)',
                  color: '#ffffff',
                }}
              >
                版本未知
              </span>
            ) : null}
          </div>

          {/* 悬浮快捷按钮 */}
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
              className="min-w-0 flex-1 truncate text-[13.5px] font-semibold"
              style={{ color: 'var(--text-strong)' }}
              title={card.name || card.fileName.replace(/\.png$/i, '')}
            >
              {card.name || card.fileName.replace(/\.png$/i, '')}
            </span>
            <span
              className="shrink-0 rounded-[5px] px-1.5 py-[1px] text-[10.5px] font-medium"
              style={toneBadgeStyle(card.type)}
              title={badgeText}
            >
              {TYPE_META[card.type].label}
            </span>
          </div>
          <div
            className="flex items-center justify-between gap-1 text-[11.5px]"
            style={{ color: 'var(--text-dim)' }}
          >
            {displayAuthor ? (
              <span
                className="inline-flex min-w-0 items-center gap-1 truncate"
                style={{ color: 'var(--text-muted)' }}
                title={`作者：${displayAuthor}`}
              >
                <UserRound size={11} className="shrink-0" style={{ color: 'var(--primary)' }} />
                <span className="truncate">{displayAuthor}</span>
              </span>
            ) : (
              <span className="truncate">{card.subtitle || card.fileName}</span>
            )}
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

          <button type="button" onClick={onPickDirectory} disabled={scanning} className="kk-btn">
            <FolderSearch size={14} />
            <span>选择目录</span>
          </button>

          <label className="flex cursor-pointer items-center gap-1.5 px-2 text-[12.5px]" style={{ color: 'var(--text-muted)' }}>
            <input
              type="checkbox"
              checked={recursive}
              disabled={scanning}
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

          {scanning && onCancelScan && (
            <button
              type="button"
              onClick={onCancelScan}
              className="kk-btn kk-btn-danger text-[12px]"
            >
              <X size={13} />
              <span>取消</span>
            </button>
          )}

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

        {/* 异步大库扫描实时进度条 */}
        {scanning && scanProgress && (
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-[12px]">
              <span className="truncate" style={{ color: 'var(--text-muted)' }}>
                {scanProgress.message || '正在增量扫描目录…'}
              </span>
              <span className="font-mono-num shrink-0 font-semibold" style={{ color: 'var(--primary)' }}>
                {scanProgress.percent}%
              </span>
            </div>
            <div className="kk-progress-bar">
              <div className="kk-progress-fill" style={{ width: `${Math.max(4, scanProgress.percent)}%` }} />
            </div>
          </div>
        )}

        {/* 第二行：分类胶囊 + 版本筛选 + 视图切换 + 作者/搜索/导出/密度 */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5">
            {(['all', 'character', 'coordinate', 'scene', 'other'] as const).map((key) => {
              const active = typeFilter === key
              const label = key === 'all' ? '全部' : TYPE_META[key].label
              const cnt = counts[key]
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => onChangeFilters({ ...filters, type: key })}
                  className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[12px] font-medium transition-colors cursor-pointer"
                  style={{
                    backgroundColor: active ? 'var(--primary)' : 'var(--surface-alt)',
                    color: active ? 'var(--on-primary)' : 'var(--text)',
                    border: `1px solid ${active ? 'var(--primary)' : 'var(--border)'}`,
                  }}
                >
                  <span>{label}</span>
                  {cnt !== null && (
                    <span
                      className="font-mono-num text-[11px]"
                      style={{ opacity: active ? 0.9 : 0.7 }}
                    >
                      {cnt}
                    </span>
                  )}
                </button>
              )
            })}

            {/* 混放多版本卡片时自动浮现的版本分段胶囊 */}
            {gameOptions.length >= 2 && (
              <div
                className="inline-flex items-center rounded-full p-0.5"
                style={{
                  backgroundColor: 'var(--surface-alt)',
                  border: '1px solid var(--border)',
                }}
              >
                <button
                  type="button"
                  onClick={() => onChangeFilters({ ...filters, game: 'all' })}
                  className="rounded-full px-2 py-0.5 text-[11.5px] font-semibold transition-colors cursor-pointer"
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
                      onClick={() => onChangeFilters({ ...filters, game: gameTag })}
                      className="font-mono-num inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11.5px] font-semibold transition-colors cursor-pointer"
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

            {/* 视图模式：平铺画廊 / 按作者分组 */}
            <div
              className="inline-flex items-center rounded-full p-0.5"
              style={{
                backgroundColor: 'var(--surface-alt)',
                border: '1px solid var(--border)',
              }}
            >
              <button
                type="button"
                onClick={() => setViewMode('grid')}
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11.5px] font-semibold transition-colors cursor-pointer"
                style={{
                  backgroundColor: viewMode === 'grid' ? 'var(--surface)' : 'transparent',
                  color: viewMode === 'grid' ? 'var(--primary)' : 'var(--text-muted)',
                }}
              >
                <LayoutGrid size={12} />
                <span>平铺</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('author')}
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11.5px] font-semibold transition-colors cursor-pointer"
                style={{
                  backgroundColor: viewMode === 'author' ? 'var(--surface)' : 'transparent',
                  color: viewMode === 'author' ? 'var(--primary)' : 'var(--text-muted)',
                }}
              >
                <Users size={12} />
                <span>按作者</span>
              </button>
            </div>

            {isDemoMode && (
              <span
                title="画廊示范样例，可直接点选试玩编辑；选择本地目录后切换为你的真实角色卡"
                className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11.5px] font-medium"
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

          <div className="flex flex-wrap items-center gap-1.5">
            {/* 作者筛选下拉（本地分页模式下始终支持筛选无作者，不把已加载作者数冒充全库统计） */}
            {(authorOptions.named.length > 0 || !isDemoMode) && (
              <select
                aria-label="按作者筛选"
                value={effectiveAuthorFilter}
                onChange={(e) => onChangeFilters({ ...filters, author: e.target.value })}
                className="kk-input h-8 w-[142px] py-0.5 text-[12px]"
              >
                <option value="all">
                  {authorCountsComplete
                    ? `全部作者 (${authorOptions.named.length})`
                    : '全部作者'}
                </option>
                {authorOptions.named.map(([author, cnt]) => (
                  <option key={author} value={author}>
                    {authorCountsComplete ? `${author} (${cnt})` : author}
                  </option>
                ))}
                {(authorOptions.unknownCount > 0 || !isDemoMode) && (
                  <option value={UNKNOWN_AUTHOR_KEY}>
                    {authorCountsComplete
                      ? `未知作者 (${authorOptions.unknownCount})`
                      : '未知作者'}
                  </option>
                )}
              </select>
            )}

            {/* 搜索框 */}
            <div className="relative w-40">
              <Search
                size={14}
                className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2"
                style={{ color: 'var(--text-dim)' }}
              />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    onChangeFilters({ ...filters, search: searchInput })
                  }
                }}
                placeholder="名称 / 作者 / 标签"
                className="kk-input h-8 py-1 pl-8 pr-7 text-[12px]"
              />
              {searchInput && (
                <button
                  type="button"
                  onClick={() => {
                    setSearchInput('')
                    onChangeFilters({ ...filters, search: '' })
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 cursor-pointer"
                  style={{ color: 'var(--text-dim)' }}
                  aria-label="清空搜索"
                >
                  <X size={13} />
                </button>
              )}
            </div>

            {!isDemoMode && exportCards.length > 0 && (
              <div className="flex items-center gap-1">
                <DataExportButton
                  kind="list"
                  paths={exportCards.map((c) => c.path)}
                  format="csv"
                  label="导出 CSV"
                  title={
                    pageMeta.hasMore
                      ? `导出当前已加载的 ${exportCards.length} 张卡片列表为 CSV`
                      : '导出当前筛选结果列表为 CSV'
                  }
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

      {/* 主体：左画廊网格/作者分组 + 右玻璃检视抽屉 */}
      <div className="flex min-h-0 flex-1 gap-4 overflow-hidden">
        {/* 画廊区 */}
        <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto pr-1">
          {/* 扫描未完成提示条（complete=false 时提醒用户当前为部分/历史缓存结果） */}
          {!isDemoMode && pageMeta.indexed && !pageMeta.complete && !scanning && (
            <div
              className="kk-surface-alt mb-3 flex flex-wrap items-center justify-between gap-2 px-3.5 py-2 text-[12px]"
              style={{ borderColor: 'var(--warning)' }}
            >
              <div className="flex items-center gap-2" style={{ color: 'var(--warning)' }}>
                <AlertTriangle size={14} className="shrink-0" />
                <span>
                  该目录范围的上次扫描尚未完成，当前展示的是已处理缓存或历史扫描成员。
                </span>
              </div>
              <button
                type="button"
                onClick={onScan}
                className="kk-btn h-7 px-2.5 text-[11.5px]"
              >
                <RefreshCw size={12} />
                <span>重新完整扫描</span>
              </button>
            </div>
          )}

          {!isDemoMode && !pageMeta.indexed && !scanning && !loadingPage ? (
            <div className="kk-surface flex h-full flex-col items-center justify-center gap-3 p-10 text-center">
              <div
                className="flex h-12 w-12 items-center justify-center rounded-full"
                style={{ backgroundColor: 'var(--warning-soft)', color: 'var(--warning)' }}
              >
                <FolderSearch size={22} />
              </div>
              <div className="text-[15px] font-semibold" style={{ color: 'var(--text-strong)' }}>
                当前扫描范围尚未建立索引
              </div>
              <p className="max-w-md text-[13px]" style={{ color: 'var(--text-muted)' }}>
                「含子目录」与仅扫描当前目录使用各自独立的索引范围，旧版缓存升级后首次访问也需要重新扫描，不能把未建索引视为真实空库。
              </p>
              <div className="mt-1 flex items-center gap-2.5">
                <button
                  type="button"
                  onClick={onScan}
                  disabled={!browseDir.trim()}
                  className="kk-btn kk-btn-primary"
                >
                  <RefreshCw size={14} />
                  <span>立即扫描建立索引</span>
                </button>
                <button type="button" onClick={onLoadDemo} className="kk-btn">
                  <Sparkles size={14} />
                  <span>查看示范画廊</span>
                </button>
              </div>
            </div>
          ) : loadingPage && filtered.length === 0 ? (
            <div className="kk-surface flex h-full flex-col items-center justify-center gap-2.5 p-10 text-center">
              <Loader2 size={24} className="animate-spin" style={{ color: 'var(--primary)' }} />
              <div className="text-[13.5px] font-medium" style={{ color: 'var(--text-muted)' }}>
                正在从索引加载卡片分页…
              </div>
            </div>
          ) : filtered.length === 0 ? (
            <div className="kk-surface flex h-full flex-col items-center justify-center gap-3 p-10 text-center">
              <div
                className="flex h-12 w-12 items-center justify-center rounded-full"
                style={{ backgroundColor: 'var(--primary-soft)', color: 'var(--primary)' }}
              >
                <FolderSearch size={22} />
              </div>
              <div className="text-[15px] font-semibold" style={{ color: 'var(--text-strong)' }}>
                {!isDemoMode &&
                filters.type === 'all' &&
                filters.game === 'all' &&
                filters.author === 'all' &&
                !filters.search.trim()
                  ? '该目录下没有扫描到卡片'
                  : cards.length === 0 && isDemoMode
                    ? '还没有扫描到角色卡'
                    : '没有符合当前筛选条件的卡片'}
              </div>
              <p className="max-w-sm text-[13px]" style={{ color: 'var(--text-muted)' }}>
                选择你的恋活 UserData 目录扫描本地角色卡，或者调整筛选条件、载入内置示范画廊。
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
          ) : viewMode === 'grid' ? (
            <div className="flex flex-col gap-3 pb-4">
              <div className={`grid gap-3.5 ${gridColsClass}`}>
                {(isDemoMode ? filtered.slice(0, demoVisibleCount) : filtered).map((card) =>
                  renderCardTile(card),
                )}
              </div>
              {isDemoMode ? (
                demoVisibleCount < filtered.length && (
                  <div className="flex items-center justify-center gap-3 py-2">
                    <span className="font-mono-num text-[12px]" style={{ color: 'var(--text-muted)' }}>
                      已显示 {demoVisibleCount} / {filtered.length} 张卡片
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        setDemoVisibleCount((prev) => Math.min(filtered.length, prev + PAGE_BATCH_SIZE))
                      }
                      className="kk-btn text-[12px]"
                    >
                      加载更多 (+{Math.min(PAGE_BATCH_SIZE, filtered.length - demoVisibleCount)})
                    </button>
                  </div>
                )
              ) : (
                <div className="flex items-center justify-center gap-3 py-2">
                  <span className="font-mono-num text-[12px]" style={{ color: 'var(--text-muted)' }}>
                    已加载 {filtered.length} / 共匹配 {pageMeta.total} 张卡片
                  </span>
                  {pageMeta.hasMore && (
                    <button
                      type="button"
                      disabled={loadingPage || scanning}
                      onClick={onLoadMore}
                      className="kk-btn text-[12px]"
                    >
                      {loadingPage ? (
                        <Loader2 size={13} className="animate-spin" />
                      ) : (
                        <RefreshCw size={13} />
                      )}
                      <span>
                        {loadingPage
                          ? '加载中…'
                          : `加载下一页 (+${Math.min(PAGE_BATCH_SIZE, Math.max(0, pageMeta.total - filtered.length))})`}
                      </span>
                    </button>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-4 pb-4">
              {!isDemoMode && pageMeta.hasMore && (
                <div className="kk-surface-alt flex flex-wrap items-center justify-between gap-2 px-3.5 py-2 text-[12px]">
                  <span style={{ color: 'var(--text-muted)' }}>
                    当前按已加载的 <strong className="font-mono-num">{filtered.length}</strong> / 共匹配{' '}
                    <strong className="font-mono-num">{pageMeta.total}</strong> 张卡片归纳作者；点击展开某个作者或「查全库」可按作者分页获取该作者全部卡片。
                  </span>
                  <button
                    type="button"
                    disabled={loadingPage || scanning}
                    onClick={onLoadMore}
                    className="kk-btn h-7 px-2.5 text-[11.5px]"
                  >
                    {loadingPage ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                    <span>加载更多卡片发现更多作者</span>
                  </button>
                </div>
              )}

              {authorGroups.map((group) => {
                const collapsed = Boolean(collapsedGroups[group.key])
                const alloc = authorBudgetPlan.allocations[group.key] ?? {
                  renderCount: 0,
                  deferredByBudget: false,
                }
                const renderedItems = collapsed ? [] : group.items.slice(0, alloc.renderCount)
                const localRemaining = Math.max(0, group.items.length - renderedItems.length)
                const canQueryMoreFromIndex = !isDemoMode && group.hasMore
                const countLabel = group.loadedFromIndex
                  ? `共 ${group.total ?? group.items.length} 张`
                  : !isDemoMode && pageMeta.hasMore
                    ? `已载入 ${group.items.length} 张`
                    : `${group.items.length} 张`

                return (
                  <section key={group.key} className="flex flex-col gap-2.5">
                    <div className="kk-surface flex items-center justify-between gap-2 px-3.5 py-2">
                      <button
                        type="button"
                        onClick={() => {
                          const nextCollapsed = !collapsed
                          setCollapsedGroups((prev) => ({ ...prev, [group.key]: nextCollapsed }))
                          if (!nextCollapsed && !isDemoMode && !group.loadedFromIndex) {
                            void loadAuthorGroupPage(group.key, group.isUnknown, false)
                          }
                        }}
                        className="flex min-w-0 flex-1 items-center gap-2 text-left cursor-pointer"
                      >
                        {collapsed ? (
                          <ChevronRight size={15} style={{ color: 'var(--text-dim)' }} />
                        ) : (
                          <ChevronDown size={15} style={{ color: 'var(--primary)' }} />
                        )}
                        <UserRound
                          size={14}
                          style={{ color: group.isUnknown ? 'var(--text-dim)' : 'var(--primary)' }}
                        />
                        <span
                          className="truncate text-[13.5px] font-semibold"
                          style={{ color: group.isUnknown ? 'var(--text-muted)' : 'var(--text-strong)' }}
                        >
                          {group.label}
                        </span>
                        <span
                          className="font-mono-num shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium"
                          style={{ backgroundColor: 'var(--surface-alt)', color: 'var(--text-muted)' }}
                        >
                          {countLabel}
                        </span>
                        {group.loading && (
                          <Loader2 size={13} className="shrink-0 animate-spin" style={{ color: 'var(--primary)' }} />
                        )}
                      </button>

                      <div className="flex shrink-0 items-center gap-2">
                        {!isDemoMode && !group.loadedFromIndex && (
                          <button
                            type="button"
                            disabled={group.loading}
                            onClick={() => {
                              setCollapsedGroups((prev) => ({ ...prev, [group.key]: false }))
                              void loadAuthorGroupPage(group.key, group.isUnknown, false)
                            }}
                            className="kk-btn h-7 px-2 text-[11.5px]"
                          >
                            <Search size={11} />
                            <span>查该作者全部</span>
                          </button>
                        )}
                        <span className="text-[11.5px]" style={{ color: 'var(--text-dim)' }}>
                          {collapsed
                            ? '点击展开'
                            : alloc.deferredByBudget && renderedItems.length === 0
                              ? '等待渲染配额'
                              : '点击折叠'}
                        </span>
                      </div>
                    </div>

                    {!collapsed && renderedItems.length > 0 && (
                      <div className={`grid gap-3.5 ${gridColsClass}`}>
                        {renderedItems.map((card) => renderCardTile(card))}
                      </div>
                    )}

                    {!collapsed && (localRemaining > 0 || canQueryMoreFromIndex) && (
                      <div className="flex flex-wrap items-center justify-center gap-2 py-1">
                        {alloc.deferredByBudget ? (
                          <button
                            type="button"
                            onClick={() => {
                              setAuthorRenderBudget((prev) => prev + PAGE_BATCH_SIZE)
                              if (!isDemoMode && !group.loadedFromIndex) {
                                void loadAuthorGroupPage(group.key, group.isUnknown, false)
                              }
                            }}
                            className="kk-btn text-[12px]"
                          >
                            <LayoutGrid size={12} />
                            <span>
                              {renderedItems.length === 0
                                ? `释放配额显示该作者卡片（+${Math.min(GROUP_INITIAL_LIMIT, group.items.length)}）`
                                : `继续显示该作者更多（已渲染 ${renderedItems.length} / ${group.items.length}）`}
                            </span>
                          </button>
                        ) : localRemaining > 0 ? (
                          <button
                            type="button"
                            onClick={() => {
                              setGroupLimits((prev) => ({
                                ...prev,
                                [group.key]: (prev[group.key] ?? GROUP_INITIAL_LIMIT) + GROUP_INITIAL_LIMIT,
                              }))
                              setAuthorRenderBudget((prev) => prev + GROUP_INITIAL_LIMIT)
                            }}
                            className="kk-btn text-[12px]"
                          >
                            <ChevronDown size={12} />
                            <span>
                              展开该作者更多卡片 ({renderedItems.length} / {group.items.length})
                            </span>
                          </button>
                        ) : null}

                        {canQueryMoreFromIndex && (
                          <button
                            type="button"
                            disabled={group.loading}
                            onClick={() => void loadAuthorGroupPage(group.key, group.isUnknown, true)}
                            className="kk-btn text-[12px]"
                          >
                            {group.loading ? (
                              <Loader2 size={12} className="animate-spin" />
                            ) : (
                              <RefreshCw size={12} />
                            )}
                            <span>
                              {group.loadedFromIndex
                                ? `从索引加载该作者下一页 (${group.items.length} / ${group.total ?? '?'})`
                                : '从索引加载该作者全部卡片'}
                            </span>
                          </button>
                        )}
                      </div>
                    )}
                  </section>
                )
              })}

              <div className="flex flex-wrap items-center justify-center gap-3 py-2">
                <span className="font-mono-num text-[12px]" style={{ color: 'var(--text-muted)' }}>
                  当前已渲染 {authorBudgetPlan.totalRendered} 张（全局上限 {authorRenderBudget} 张）
                </span>
                {authorBudgetPlan.hasDeferredCards && (
                  <button
                    type="button"
                    onClick={() => setAuthorRenderBudget((prev) => prev + PAGE_BATCH_SIZE)}
                    className="kk-btn text-[12px]"
                  >
                    <LayoutGrid size={13} />
                    <span>增加显示配额 (+{PAGE_BATCH_SIZE})</span>
                  </button>
                )}
              </div>
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
                    {formatCardTypeBadge(selectedCard.type, selectedCard.game)}
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
                  <span style={{ color: 'var(--text-dim)' }}>作者</span>
                  {(() => {
                    const cleanAuthor = normalizeDisplayAuthor(selectedCard.author)
                    return (
                      <span
                        className="truncate font-medium"
                        style={{ color: cleanAuthor ? 'var(--text-strong)' : 'var(--text-dim)' }}
                        title={cleanAuthor || '未知作者'}
                      >
                        {cleanAuthor || '未知作者'}
                        {cleanAuthor && selectedCard.authorSource && AUTHOR_SOURCE_LABEL[selectedCard.authorSource]
                          ? ` · ${AUTHOR_SOURCE_LABEL[selectedCard.authorSource]}`
                          : ''}
                      </span>
                    )
                  })()}
                </div>
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
                <>
                  <CardAuthorEditor
                    key={`author-${selectedCard.path}`}
                    path={selectedCard.path}
                    initialAuthor={normalizeDisplayAuthor(selectedCard.author)}
                    initialSource={normalizeDisplayAuthor(selectedCard.author) ? selectedCard.authorSource : ''}
                    initialHistory={selectedCard.authorHistory}
                    userId={normalizeUserId(selectedCard.userId)}
                    onSaved={(author, source, history) => {
                      const cleanAuthor = normalizeDisplayAuthor(author)
                      onAuthorSaved(selectedCard.path, cleanAuthor, cleanAuthor ? source : '', history)
                      setAuthorGroupPages((prev) => {
                        const next: Record<string, AuthorGroupPageState> = {}
                        for (const [k, v] of Object.entries(prev)) {
                          next[k] = {
                            ...v,
                            items: v.items.map((c) =>
                              c.path === selectedCard.path
                                ? { ...c, author: cleanAuthor, authorSource: cleanAuthor ? source : '', authorHistory: history }
                                : c,
                            ),
                          }
                        }
                        return next
                      })
                    }}
                    onNotify={onNotify}
                    onLog={onLog}
                  />
                  <CardTagEditor
                    key={`tags-${selectedCard.path}`}
                    path={selectedCard.path}
                    onSaved={(tags) => {
                      onTagsSaved(selectedCard.path, tags)
                      setAuthorGroupPages((prev) => {
                        const next: Record<string, AuthorGroupPageState> = {}
                        for (const [k, v] of Object.entries(prev)) {
                          next[k] = {
                            ...v,
                            items: v.items.map((c) =>
                              c.path === selectedCard.path ? { ...c, tags } : c,
                            ),
                          }
                        }
                        return next
                      })
                    }}
                    onNotify={onNotify}
                    onLog={onLog}
                  />
                </>
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
                <div className="flex items-center gap-1.5">
                  {(selectedCard.type === 'character' ||
                    selectedCard.type === 'coordinate' ||
                    selectedCard.type === 'scene') && (
                    <ConvertCardButton
                      path={selectedCard.path}
                      cardType={selectedCard.type}
                      game={selectedCard.game}
                      className="kk-btn flex-1 py-1.5 text-[12px]"
                      onConverted={onCardConverted}
                      onNotify={onNotify}
                      onLog={onLog}
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => onRevealFile(selectedCard.path)}
                    title="在资源管理器中定位"
                    className={
                      selectedCard.type === 'character' ||
                      selectedCard.type === 'coordinate' ||
                      selectedCard.type === 'scene'
                        ? 'kk-btn shrink-0 px-2.5 py-1.5 text-[12px]'
                        : 'kk-btn w-full py-1.5 text-[12px]'
                    }
                  >
                    <ExternalLink size={13} />
                    <span>
                      {selectedCard.type === 'character' ||
                      selectedCard.type === 'coordinate' ||
                      selectedCard.type === 'scene'
                        ? '定位'
                        : '在资源管理器中定位'}
                    </span>
                  </button>
                </div>
              )}
            </div>
          </aside>
        )}
      </div>
    </div>
  )
}
