import React, { useCallback, useEffect, useRef, useState } from 'react'
import { AppShell } from './components/AppShell'
import { CardEditorModal } from './components/CardEditorModal'
import { ConfirmModal, type ConfirmDialogState } from './components/ConfirmModal'
import { KK_PERSONALITIES, mapLegacyTheme } from './data/constants'
import { DEMO_CARDS, makeDemoDetail } from './data/demoCards'
import { backend, cancelAndReleaseTask, waitTask } from './lib/bridge'
import { BrowserPage, type BrowserFilterState, type BrowserPageMeta } from './pages/BrowserPage'
import { EditorPage } from './pages/EditorPage'
import { SettingsPage, type UpdateUiState } from './pages/SettingsPage'
import { LogPage, ModPage, PackPage, ScenePage, SharePage } from './pages/WorkspacePages'
import type {
  AppConfig,
  CardDetail,
  CardModCheckResult,
  CardPageQueryOptions,
  CardSummary,
  CardType,
  LogEntry,
  ModSummaryItem,
  PageId,
  PagedScanResult,
  SceneAnalysisResult,
  ThemeId,
  UpdateInfo,
  UpdateReleaseInfo,
} from './types/kk'

const DEFAULT_CONFIG: AppConfig = {
  kk_game_dir: '',
  kks_game_dir: '',
  mod_dirs: [],
  output_dir: '',
  last_browse_dir: '',
  carrier_dir: '',
  pack_out_dir: '',
  theme: 'sora_light',
  wallpaper_path: '',
  wallpaper_url: '',
  wallpaper_enabled: true,
  wallpaper_overlay: 52,
  wallpaper_panel_alpha: 84,
  wallpaper_blur: 18,
  ui_mode: 'normal',
  start_page: 1,
  recent_cards: [],
  app_version: 'v0.6.0',
  is_frozen: false,
}

const INITIAL_UPDATE_STATE: UpdateUiState = {
  stage: 'idle',
  stageText: '',
  percent: 0,
  downloadedBytes: 0,
  totalBytes: 0,
  release: null,
  artifactPath: '',
  errorText: '',
}

const PAGE_DEFAULT_STATUS: Record<PageId, string> = {
  browser: '就绪 · 单击卡片预览档案，双击角色卡原地弹出编辑浮层',
  editor: '就绪 · 仅重写修改过的 Parameter 块，其余卡片数据原样保留',
  scene: '就绪 · 选择 Studio 场景卡分析内嵌角色与引用 Mod',
  pack: '就绪 · 支持标准 ZIP、图种/视频载体、多层加密与分卷完整性校验',
  share: '就绪 · 同名卡自动防覆盖保留，自动提取并打包依赖 Mod',
  mod: '就绪 · 支持增量索引缓存、单卡缺失检测与未引用 Mod 归档',
  log: '就绪 · 显示本次会话的全部核心操作记录',
  settings: '就绪 · 主题与壁纸参数实时生效，点击「保存全部设置」写入 config.json',
}

function nowTime() {
  return new Date().toTimeString().slice(0, 8)
}

export const App: React.FC = () => {
  const [activePage, setActivePage] = useState<PageId>('browser')
  const [config, setConfig] = useState<AppConfig>(DEFAULT_CONFIG)
  const [theme, setTheme] = useState<ThemeId>('sora_light')
  const [statusOverride, setStatusOverride] = useState<string | null>(null)
  const [toast, setToast] = useState<{ text: string; tone: 'info' | 'ok' | 'warn' | 'error' } | null>(null)
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState | null>(null)
  const toastTimer = useRef<number | null>(null)
  const statusText = statusOverride ?? PAGE_DEFAULT_STATUS[activePage]

  // 浏览画廊状态
  const [cards, setCards] = useState<CardSummary[]>(DEMO_CARDS)
  const [isDemoMode, setIsDemoMode] = useState(true)
  const [browseDir, setBrowseDir] = useState('')
  const [scannedDir, setScannedDir] = useState('')
  const [recursive, setRecursive] = useState(false)
  const [scanningCards, setScanningCards] = useState(false)
  const [scanProgress, setScanProgress] = useState<{ percent: number; message: string } | null>(null)
  const [loadingPage, setLoadingPage] = useState(false)
  const [browserFilters, setBrowserFilters] = useState<BrowserFilterState>({
    type: 'all',
    game: 'all',
    author: 'all',
    search: '',
  })
  const [pageMeta, setPageMeta] = useState<BrowserPageMeta>({
    total: DEMO_CARDS.length,
    hasMore: false,
    indexed: true,
    complete: true,
    versionCounts: [],
  })
  const activeScanTaskId = useRef<string | null>(null)
  const scanSeqRef = useRef(0)
  const querySeqRef = useRef(0)
  const cardsRef = useRef<CardSummary[]>(DEMO_CARDS)
  const filtersRef = useRef<BrowserFilterState>(browserFilters)
  const scannedDirRef = useRef(scannedDir)
  const recursiveRef = useRef(recursive)
  const loadingPageRef = useRef(false)
  cardsRef.current = cards
  filtersRef.current = browserFilters
  scannedDirRef.current = scannedDir
  recursiveRef.current = recursive
  loadingPageRef.current = loadingPage

  // 角色编辑状态（独立页）
  const [editorCard, setEditorCard] = useState<CardDetail | null>(() => makeDemoDetail(DEMO_CARDS[0]))
  const [editorOriginal, setEditorOriginal] = useState<CardDetail | null>(() =>
    makeDemoDetail(DEMO_CARDS[0]),
  )
  const [pendingCoverPath, setPendingCoverPath] = useState('')
  const [pendingCoverUrl, setPendingCoverUrl] = useState('')
  const [editorDirty, setEditorDirty] = useState(false)
  const [savingCard, setSavingCard] = useState(false)
  const [editorModCheck, setEditorModCheck] = useState<CardModCheckResult | null>(null)
  const [checkingEditorMods, setCheckingEditorMods] = useState(false)

  // 画廊原地编辑浮层状态（与独立编辑页互相隔离，不丢画廊上下文）
  const [modalCard, setModalCard] = useState<CardDetail | null>(null)
  const [modalOriginal, setModalOriginal] = useState<CardDetail | null>(null)
  const [modalCoverPath, setModalCoverPath] = useState('')
  const [modalCoverUrl, setModalCoverUrl] = useState('')
  const [modalDirty, setModalDirty] = useState(false)
  const [modalSaving, setModalSaving] = useState(false)
  const [modalModCheck, setModalModCheck] = useState<CardModCheckResult | null>(null)
  const [modalCheckingMods, setModalCheckingMods] = useState(false)

  // Mod / 场景 / 更新 / 日志 / 设置状态
  const [mods, setMods] = useState<ModSummaryItem[]>([])
  const [scanningMods, setScanningMods] = useState(false)
  const [modScanProgress, setModScanProgress] = useState('')
  const [sceneResult, setSceneResult] = useState<SceneAnalysisResult | null>(null)
  const [analyzingScene, setAnalyzingScene] = useState(false)
  const [extractingScene, setExtractingScene] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null)
  const [updateState, setUpdateState] = useState<UpdateUiState>(INITIAL_UPDATE_STATE)
  const [logs, setLogs] = useState<LogEntry[]>([
    {
      id: 'init-1',
      time: nowTime(),
      level: 'info',
      source: 'UI',
      message: 'KKTools 日系清爽工作台已启动（复用纯 Python core/ 内核）',
    },
  ])

  const appendLog = useCallback((level: LogEntry['level'], source: string, message: string) => {
    void backend.recordLog(level, source, message)
    setLogs((prev) => [
      { id: `${Date.now()}-${Math.random()}`, time: nowTime(), level, source, message },
      ...prev.slice(0, 199),
    ])
  }, [])

  const notify = useCallback(
    (text: string, tone: 'info' | 'ok' | 'warn' | 'error' = 'info') => {
      setToast({ text, tone })
      setStatusOverride(text)
      if (toastTimer.current) window.clearTimeout(toastTimer.current)
      toastTimer.current = window.setTimeout(() => {
        setToast(null)
        setStatusOverride(null)
      }, 3500)
    },
    [],
  )

  // 同步脏状态给后端（独立页或浮层任一处有真实未保存改动均触发关窗保护）
  useEffect(() => {
    const hasRealDirty =
      (editorDirty && !editorCard?.isDemo) || (modalDirty && !modalCard?.isDemo)
    void backend.setDirtyState(hasRealDirty)
  }, [editorDirty, editorCard?.isDemo, modalDirty, modalCard?.isDemo])

  // 将主题与壁纸毛玻璃令牌同步到 <html>
  useEffect(() => {
    const root = document.documentElement
    root.setAttribute('data-theme', theme)
    const wallOn = Boolean(config.wallpaper_enabled && config.wallpaper_url)
    root.setAttribute('data-wallpaper', wallOn ? 'on' : 'off')
    root.style.setProperty('--overlay-alpha', String(config.wallpaper_overlay / 100))
    root.style.setProperty('--panel-alpha', String(config.wallpaper_panel_alpha / 100))
    root.style.setProperty('--glass-blur', `${config.wallpaper_blur}px`)
  }, [
    theme,
    config.wallpaper_enabled,
    config.wallpaper_url,
    config.wallpaper_overlay,
    config.wallpaper_panel_alpha,
    config.wallpaper_blur,
  ])

  useEffect(() => {
    const onCloseBlocked = () => notify('仍有后台任务或卡片保存尚未完成，请等待完成后退出', 'warn')
    window.addEventListener('kk-close-blocked', onCloseBlocked)
    return () => window.removeEventListener('kk-close-blocked', onCloseBlocked)
  }, [notify])

  const fetchVersionCounts = useCallback(async (dir: string, rec: boolean): Promise<Array<[string, number]>> => {
    const games: Array<'KK' | 'KKS' | 'EC'> = ['KK', 'KKS', 'EC']
    const results = await Promise.all(
      games.map(async (g) => {
        const r = await backend.queryCardPage(dir, { recursive: rec, offset: 0, limit: 1, game: g })
        if (r.ok && r.data && r.data.indexed && r.data.total > 0) {
          return [g, r.data.total] as [string, number]
        }
        return null
      }),
    )
    return results.filter((x): x is [string, number] => x !== null)
  }, [])

  const buildPageQueryOptions = useCallback(
    (rec: boolean, filters: BrowserFilterState, offset: number, limit = 120): CardPageQueryOptions => {
      const opts: CardPageQueryOptions = {
        recursive: rec,
        offset,
        limit,
      }
      if (filters.type !== 'all') opts.type = filters.type as CardType
      if (filters.game !== 'all') opts.game = filters.game as CardPageQueryOptions['game']
      if (filters.author === '__UNKNOWN__') opts.author = ''
      else if (filters.author !== 'all') opts.author = filters.author
      if (filters.search.trim()) opts.search = filters.search.trim()
      return opts
    },
    [],
  )

  const queryLocalPage = useCallback(
    async (opts: {
      dir: string
      recursive: boolean
      filters: BrowserFilterState
      append: boolean
      refreshVersions?: boolean
    }) => {
      const targetDir = opts.dir.trim()
      if (!targetDir) return null
      if (opts.append && loadingPageRef.current) return null

      const seq = ++querySeqRef.current
      const offset = opts.append ? cardsRef.current.length : 0
      setLoadingPage(true)
      const queryOpts = buildPageQueryOptions(opts.recursive, opts.filters, offset, 120)

      const [res, versionCounts] = await Promise.all([
        backend.queryCardPage(targetDir, queryOpts),
        opts.refreshVersions ? fetchVersionCounts(targetDir, opts.recursive) : Promise.resolve(null),
      ])

      if (seq !== querySeqRef.current) return null
      setLoadingPage(false)

      if (!res.ok || !res.data) {
        notify(`查询索引分页失败：${res.error || '未知错误'}`, 'error')
        appendLog('error', 'SCAN', `查询索引分页失败：${res.error || targetDir}`)
        return null
      }

      const page = res.data
      setCards((prev) => {
        if (!opts.append) return page.items
        const seen = new Set(prev.map((c) => c.id))
        const next = [...prev]
        for (const item of page.items) {
          if (!seen.has(item.id)) {
            seen.add(item.id)
            next.push(item)
          }
        }
        return next
      })
      setPageMeta((prev) => ({
        total: page.total,
        hasMore: page.hasMore,
        indexed: page.indexed,
        complete: page.complete,
        versionCounts: versionCounts ?? prev.versionCounts,
      }))
      return page
    },
    [appendLog, buildPageQueryOptions, fetchVersionCounts, notify],
  )

  // 组件卸载时取消并释放运行中的扫描任务
  useEffect(() => {
    return () => {
      const tid = activeScanTaskId.current
      if (tid) {
        activeScanTaskId.current = null
        void cancelAndReleaseTask(tid)
      }
    }
  }, [])

  // 初始化读取后端真实配置、更新状态与缓存 Mod 索引
  useEffect(() => {
    let cancelled = false

    const init = async () => {
      const [cfgRes, upRes, modCacheRes] = await Promise.all([
        backend.getConfig(),
        backend.getUpdateInfo(),
        backend.getCachedMods(),
      ])
      if (cancelled) return

      if (upRes.ok && upRes.data) {
        setUpdateInfo(upRes.data)
      }
      if (modCacheRes.ok && modCacheRes.data && modCacheRes.data.total > 0) {
        setMods(modCacheRes.data.items)
      }

      if (!cfgRes.ok || !cfgRes.data) return
      const loaded = cfgRes.data
      setConfig(loaded)
      setTheme(mapLegacyTheme(loaded.theme))
      if (loaded.last_browse_dir) {
        setBrowseDir((prev) => prev || loaded.last_browse_dir)
      }
      appendLog(
        'ok',
        'CORE',
        `已读取配置 config.json（版本 ${loaded.app_version}${loaded.wallpaper_path ? ' · 已载入本地壁纸' : ''}）`,
      )

      if (loaded.last_browse_dir) {
        const myScanSeq = ++scanSeqRef.current
        setScanningCards(true)
        setScanProgress({ percent: 5, message: '正在从增量索引载入上次浏览目录…' })
        const startRes = await backend.startScanDirectory(loaded.last_browse_dir, false, true)
        if (!cancelled && myScanSeq === scanSeqRef.current && startRes.ok && startRes.data) {
          activeScanTaskId.current = startRes.data.taskId
          const done = await waitTask<PagedScanResult>(
            startRes.data.taskId,
            (st) => {
              if (!cancelled && myScanSeq === scanSeqRef.current) {
                setScanProgress({ percent: st.percent, message: st.message })
              }
            },
          )
          if (activeScanTaskId.current === startRes.data.taskId) {
            activeScanTaskId.current = null
          }
          if (!cancelled && myScanSeq === scanSeqRef.current) {
            setScanningCards(false)
            setScanProgress(null)
            if (done.ok) {
              const resetFilters: BrowserFilterState = {
                type: 'all',
                game: 'all',
                author: 'all',
                search: '',
              }
              setBrowserFilters(resetFilters)
              setScannedDir(loaded.last_browse_dir)
              const page = await queryLocalPage({
                dir: loaded.last_browse_dir,
                recursive: false,
                filters: resetFilters,
                append: false,
                refreshVersions: true,
              })
              if (!cancelled && page && page.indexed && page.total > 0) {
                setIsDemoMode(false)
                appendLog(
                  'ok',
                  'SCAN',
                  `自动索引目录，共 ${page.total} 张本地卡片（已加载首页 ${page.items.length} 张）`,
                )
              } else if (!cancelled) {
                setCards(DEMO_CARDS)
                setIsDemoMode(true)
              }
            }
          }
        } else if (!cancelled && myScanSeq === scanSeqRef.current) {
          setScanningCards(false)
          setScanProgress(null)
        }
      }
    }

    if (window.pywebview?.api) {
      void init()
    } else {
      const onReady = () => void init()
      window.addEventListener('pywebviewready', onReady, { once: true })
      const timer = window.setTimeout(() => void init(), 180)
      return () => {
        cancelled = true
        window.removeEventListener('pywebviewready', onReady)
        window.clearTimeout(timer)
      }
    }

    return () => {
      cancelled = true
    }
  }, [appendLog, queryLocalPage])

  const handleCancelScan = useCallback(async () => {
    const tid = activeScanTaskId.current
    if (!tid) return
    await backend.cancelTask(tid)
  }, [])

  const handleScanDir = useCallback(
    async (targetDir?: string, overrideRecursive?: boolean) => {
      const dir = (targetDir ?? browseDir).trim()
      const useRecursive = overrideRecursive ?? recursiveRef.current
      if (!dir) {
        notify('请先选择角色卡所在目录', 'warn')
        return
      }
      if (activeScanTaskId.current) {
        const prevTid = activeScanTaskId.current
        activeScanTaskId.current = null
        await cancelAndReleaseTask(prevTid)
      }
      const myScanSeq = ++scanSeqRef.current
      const sameScope =
        !isDemoMode &&
        scannedDirRef.current.trim().toLowerCase() === dir.toLowerCase() &&
        recursiveRef.current === useRecursive
      const nextFilters: BrowserFilterState = sameScope
        ? filtersRef.current
        : { type: 'all', game: 'all', author: 'all', search: '' }

      if (!sameScope) {
        setBrowserFilters(nextFilters)
      }
      setScannedDir(dir)
      setIsDemoMode(false)
      setScanningCards(true)
      setScanProgress({ percent: 4, message: '正在遍历目录并更新增量索引…' })

      const startRes = await backend.startScanDirectory(dir, useRecursive, true)
      if (myScanSeq !== scanSeqRef.current) return
      if (!startRes.ok || !startRes.data) {
        setScanningCards(false)
        setScanProgress(null)
        notify(`扫描失败：${startRes.error || '未知错误'}`, 'error')
        appendLog('error', 'SCAN', `目录扫描失败：${startRes.error || dir}`)
        return
      }
      activeScanTaskId.current = startRes.data.taskId
      const done = await waitTask<PagedScanResult>(startRes.data.taskId, (st) => {
        if (myScanSeq === scanSeqRef.current) {
          setScanProgress({ percent: st.percent, message: st.message })
        }
      })
      if (activeScanTaskId.current === startRes.data.taskId) {
        activeScanTaskId.current = null
      }
      if (myScanSeq !== scanSeqRef.current) return

      setScanningCards(false)
      setScanProgress(null)

      if (done.cancelled) {
        notify('已取消目录扫描（已处理缓存可继续浏览）', 'info')
        appendLog('info', 'SCAN', `已取消扫描：${dir}`)
        await queryLocalPage({
          dir,
          recursive: useRecursive,
          filters: filtersRef.current,
          append: false,
          refreshVersions: true,
        })
        return
      }

      if (!done.ok) {
        notify(`扫描失败：${done.error || '未知错误'}`, 'error')
        appendLog('error', 'SCAN', `目录扫描失败：${done.error || dir}`)
        return
      }

      // 即使任务结果已过期 (resultExpired=true)，仍从 SQLite 索引查询第一页，不判扫描失败
      const page = await queryLocalPage({
        dir,
        recursive: useRecursive,
        filters: filtersRef.current,
        append: false,
        refreshVersions: true,
      })
      if (!page) return
      const totalCount = done.data?.total ?? page.total
      notify(`扫描完成，共索引 ${totalCount} 张卡片（已加载首页 ${page.items.length} 张）`, 'ok')
      appendLog(
        'ok',
        'SCAN',
        `扫描 ${dir} 完成（含子目录=${useRecursive}），共 ${totalCount} 项${done.resultExpired ? '（从索引重载）' : ''}`,
      )
    },
    [browseDir, isDemoMode, notify, appendLog, queryLocalPage],
  )

  const handleToggleRecursive = useCallback(() => {
    const nextRec = !recursiveRef.current
    setRecursive(nextRec)
    if (!isDemoMode && scannedDirRef.current.trim()) {
      const resetFilters: BrowserFilterState = {
        type: 'all',
        game: 'all',
        author: 'all',
        search: '',
      }
      setBrowserFilters(resetFilters)
      void queryLocalPage({
        dir: scannedDirRef.current,
        recursive: nextRec,
        filters: resetFilters,
        append: false,
        refreshVersions: true,
      })
    }
  }, [isDemoMode, queryLocalPage])

  const handleBrowserFiltersChange = useCallback(
    (next: BrowserFilterState) => {
      filtersRef.current = next
      setBrowserFilters(next)
      if (!isDemoMode && scannedDirRef.current.trim()) {
        void queryLocalPage({
          dir: scannedDirRef.current,
          recursive: recursiveRef.current,
          filters: next,
          append: false,
        })
      }
    },
    [isDemoMode, queryLocalPage],
  )

  const handleLoadMoreCards = useCallback(() => {
    if (isDemoMode || !scannedDirRef.current.trim()) return
    if (!pageMeta.hasMore || loadingPageRef.current) return
    void queryLocalPage({
      dir: scannedDirRef.current,
      recursive: recursiveRef.current,
      filters: filtersRef.current,
      append: true,
    })
  }, [isDemoMode, pageMeta.hasMore, queryLocalPage])

  const handlePickBrowseDir = async () => {
    const res = await backend.pickDirectory('选择角色卡目录', browseDir)
    if (res.ok && res.data) {
      setBrowseDir(res.data)
      await handleScanDir(res.data)
    }
  }

  const openCardPayload = (detail: CardDetail, msg: string, tone: 'info' | 'ok' = 'ok') => {
    setEditorCard(detail)
    setEditorOriginal(structuredClone(detail))
    setPendingCoverPath('')
    setPendingCoverUrl('')
    setEditorModCheck(null)
    setEditorDirty(false)
    setActivePage('editor')
    notify(msg, tone)
  }

  const syncCardSummaryInGallery = (updated: CardDetail, newCoverUrl?: string) => {
    const nextName =
      [updated.parameter.lastname, updated.parameter.firstname].filter(Boolean).join(' ') ||
      updated.fileName
    const pObj = KK_PERSONALITIES.find((x) => x.id === updated.parameter.personality)
    setCards((prev) =>
      prev.map((c) =>
        c.path === updated.path
          ? {
              ...c,
              name: nextName,
              personalityLabel: pObj ? pObj.label : c.personalityLabel,
              thumbnailUrl: newCoverUrl || c.thumbnailUrl,
            }
          : c,
      ),
    )
  }

  const handleQuickEditCard = async (card: CardSummary) => {
    if (card.isDemo) {
      const detail = makeDemoDetail(card)
      setModalCard(detail)
      setModalOriginal(structuredClone(detail))
      setModalCoverPath('')
      setModalCoverUrl('')
      setModalModCheck(null)
      setModalDirty(false)
      return
    }
    const res = await backend.loadCard(card.path)
    if (!res.ok || !res.data) {
      notify(`读取角色卡失败：${res.error || '可能不是角色卡文件'}`, 'error')
      appendLog('error', 'EDITOR', `读取失败：${card.path} (${res.error})`)
      return
    }
    setModalCard(res.data)
    setModalOriginal(structuredClone(res.data))
    setModalCoverPath('')
    setModalCoverUrl('')
    setModalModCheck(null)
    setModalDirty(false)
    appendLog('ok', 'EDITOR', `弹窗载入角色卡：${card.path}`)
  }

  const handleInspectSceneFromGallery = async (card: CardSummary) => {
    if (card.isDemo) {
      setActivePage('scene')
      notify('示范场景卡仅作展示；请在场景卡页选择本地 Studio 场景卡 PNG 解析', 'info')
      return
    }
    setActivePage('scene')
    setAnalyzingScene(true)
    const res = await backend.analyzeScene(card.path)
    setAnalyzingScene(false)
    if (!res.ok || !res.data) {
      notify(`场景卡解析失败：${res.error || '格式不匹配'}`, 'error')
      return
    }
    setSceneResult(res.data)
    notify(`场景解析完成：发现 ${res.data.characterCount} 名内嵌角色`, 'ok')
    appendLog('ok', 'SCENE', `分析场景卡：${res.data.fileName}`)
  }

  const closeModalNow = () => {
    setModalCard(null)
    setModalOriginal(null)
    setModalCoverPath('')
    setModalCoverUrl('')
    setModalModCheck(null)
    setModalDirty(false)
  }

  const handleRequestCloseModal = () => {
    if (modalSaving) return
    if (modalDirty) {
      setConfirmDialog({
        title: '关闭编辑浮层？',
        message: '当前角色卡还有未保存的改动，关闭后将放弃这些修改。',
        confirmLabel: '放弃改动并关闭',
        danger: true,
        onConfirm: closeModalNow,
      })
      return
    }
    closeModalNow()
  }

  const requestReplaceEditor = (action: () => void) => {
    if (savingCard) return
    if (editorDirty) {
      setConfirmDialog({
        title: '替换当前编辑中的角色卡？',
        message: '当前角色卡有未保存的改动，继续将放弃这些修改。',
        confirmLabel: '放弃改动并继续',
        danger: true,
        onConfirm: action,
      })
    } else action()
  }

  const handleExpandModalToPage = () => {
    if (!modalCard || modalSaving) return
    requestReplaceEditor(() => {
      setEditorCard(modalCard)
      setEditorOriginal(modalOriginal)
      setPendingCoverPath(modalCoverPath)
      setPendingCoverUrl(modalCoverUrl)
      setEditorModCheck(modalModCheck)
      setEditorDirty(modalDirty)
      closeModalNow()
      setActivePage('editor')
    })
  }

  const executeSaveModalCard = async (overwrite: boolean) => {
    if (!modalCard) return
    if (modalCard.isDemo) {
      syncCardSummaryInGallery(modalCard, modalCoverUrl || undefined)
      setModalOriginal(structuredClone(modalCard))
      setModalDirty(false)
      notify('示范档案修改已同步更新到画廊预览（本地真卡会直接安全写盘）', 'ok')
      return
    }
    setModalSaving(true)
    const res = await backend.saveCard({
      path: modalCard.path,
      overwrite,
      parameter: modalCard.parameter,
      coverPath: modalCoverPath || undefined,
    })
    setModalSaving(false)
    if (!res.ok || !res.data) {
      notify(`保存失败：${res.error || '未知错误'}`, 'error')
      appendLog('error', 'EDITOR', `保存失败：${res.error}`)
      return
    }
    if (overwrite) {
      syncCardSummaryInGallery(modalCard, modalCoverUrl || undefined)
    }
    const savedCard = { ...modalCard, path: res.data.savedPath, fileName: res.data.savedPath.split(/[\\/]/).pop() || modalCard.fileName }
    setModalCard(savedCard)
    setModalOriginal(structuredClone(savedCard))
    setModalCoverPath('')
    setModalDirty(false)
    if (res.data.warning) {
      notify(res.data.warning, 'warn')
      appendLog('warn', 'EDITOR', res.data.warning)
    } else {
      notify(`已保存到：${res.data.savedPath}`, 'ok')
    }
    appendLog('ok', 'EDITOR', `保存成功：${res.data.savedPath}`)
  }

  const handleSaveModalCard = (overwrite: boolean) => {
    if (overwrite && modalCard && !modalCard.isDemo) {
      setConfirmDialog({
        title: '确认覆盖保存原角色卡？',
        message: `将直接写回原文件（写入前会自动生成 .bak 备份）：\n${modalCard.path}`,
        confirmLabel: '确认覆盖保存',
        onConfirm: () => void executeSaveModalCard(true),
      })
      return
    }
    void executeSaveModalCard(overwrite)
  }

  const handlePickCardFile = async () => {
    const res = await backend.pickCardFile('选择恋活角色卡 PNG')
    if (res.ok && res.data) {
      const loadRes = await backend.loadCard(res.data)
      if (!loadRes.ok || !loadRes.data) {
        notify(`读取失败：${loadRes.error || '不是有效的角色卡'}`, 'error')
        return
      }
      requestReplaceEditor(() => openCardPayload(loadRes.data!, `已打开：${loadRes.data!.fileName}`, 'ok'))
    }
  }

  const handlePickCover = async () => {
    const res = await backend.pickImageFile('选择新封面图片 (PNG)')
    if (!res.ok || !res.data) return
    const urlRes = await backend.getWallpaperDataUrl(res.data)
    if (urlRes.ok && urlRes.data) {
      setPendingCoverPath(res.data)
      setPendingCoverUrl(urlRes.data)
      setEditorDirty(true)
      notify('已选定新封面，保存角色卡时生效', 'info')
    }
  }

  const handleUpdateParam = (updater: (p: CardDetail['parameter']) => CardDetail['parameter']) => {
    setEditorCard((prev) => {
      if (!prev) return prev
      return { ...prev, parameter: updater(prev.parameter) }
    })
    setEditorDirty(true)
  }

  const executeSaveCard = async (overwrite: boolean) => {
    if (!editorCard) return
    if (editorCard.isDemo) {
      setEditorOriginal(structuredClone(editorCard))
      setEditorDirty(false)
      notify('示范档案修改已即时预览（本地真实角色卡会直接安全写盘并备份）', 'ok')
      return
    }
    setSavingCard(true)
    const res = await backend.saveCard({
      path: editorCard.path,
      overwrite,
      parameter: editorCard.parameter,
      coverPath: pendingCoverPath || undefined,
    })
    setSavingCard(false)
    if (!res.ok || !res.data) {
      notify(`保存失败：${res.error || '未知错误'}`, 'error')
      appendLog('error', 'EDITOR', `保存失败：${res.error}`)
      return
    }
    if (overwrite) syncCardSummaryInGallery(editorCard, pendingCoverUrl || undefined)
    const savedCard = { ...editorCard, path: res.data.savedPath, fileName: res.data.savedPath.split(/[\\/]/).pop() || editorCard.fileName }
    setEditorCard(savedCard)
    setEditorOriginal(structuredClone(savedCard))
    setPendingCoverPath('')
    setEditorDirty(false)
    if (res.data.warning) {
      notify(res.data.warning, 'warn')
      appendLog('warn', 'EDITOR', res.data.warning)
    } else {
      notify(`已保存到：${res.data.savedPath}`, 'ok')
    }
    appendLog('ok', 'EDITOR', `保存成功：${res.data.savedPath}`)
  }

  const handleSaveCard = (overwrite: boolean) => {
    if (overwrite && editorCard && !editorCard.isDemo) {
      setConfirmDialog({
        title: '确认覆盖保存原角色卡？',
        message: `将直接写回原文件（写入前会自动生成 .bak 备份）：\n${editorCard.path}`,
        confirmLabel: '确认覆盖保存',
        onConfirm: () => void executeSaveCard(true),
      })
      return
    }
    void executeSaveCard(overwrite)
  }

  const handleCheckEditorMods = async () => {
    if (!editorCard || editorCard.isDemo) return
    setCheckingEditorMods(true)
    const res = await backend.checkCardMods(editorCard.path)
    setCheckingEditorMods(false)
    if (!res.ok || !res.data) {
      notify(`缺失检测失败：${res.error}`, 'error')
      return
    }
    setEditorModCheck(res.data)
    notify(
      `检测完成：已装 ${res.data.present.length} 项，缺失 ${res.data.missing.length} 项`,
      res.data.missing.length > 0 ? 'warn' : 'ok',
    )
  }

  const handleSaveConfig = async () => {
    setSavingConfig(true)
    const res = await backend.saveConfig({ ...config, theme })
    setSavingConfig(false)
    if (!res.ok || !res.data) {
      notify(`配置保存失败：${res.error || '未知错误'}`, 'error')
      return
    }
    setConfig(res.data)
    notify('外观与路径配置已写入 config.json', 'ok')
    appendLog('ok', 'CONFIG', `已保存主题 ${theme} 与壁纸/路径配置`)
  }

  const handlePickWallpaper = async () => {
    const res = await backend.pickImageFile('选择背景壁纸图片')
    if (res.ok && res.data) {
      const dataUrlRes = await backend.getWallpaperDataUrl(res.data)
      if (dataUrlRes.ok && dataUrlRes.data) {
        setConfig((prev) => ({
          ...prev,
          wallpaper_path: res.data!,
          wallpaper_url: dataUrlRes.data!,
          wallpaper_enabled: true,
        }))
        notify('已载入新壁纸并启用毛玻璃融合', 'ok')
      }
    }
  }

  const handleScanMods = async () => {
    setScanningMods(true)
    setModScanProgress('正在准备扫描 Mod 目录…')
    const dirs: string[] = []
    if (config.kk_game_dir) dirs.push(`${config.kk_game_dir}/mods`)
    if (config.kks_game_dir) dirs.push(`${config.kks_game_dir}/mods`)
    dirs.push(...config.mod_dirs)

    const startRes = await backend.startScanMods(dirs)
    if (!startRes.ok || !startRes.data) {
      setScanningMods(false)
      setModScanProgress('')
      notify(`Mod 扫描失败：${startRes.error || '未配置目录'}`, 'warn')
      return
    }
    const done = await waitTask<{ total: number; items: ModSummaryItem[] }>(
      startRes.data.taskId,
      (st) => setModScanProgress(st.message),
    )
    setScanningMods(false)
    setModScanProgress('')
    if (!done.ok || !done.data) {
      notify(`Mod 索引失败：${done.error}`, 'error')
      return
    }
    setMods(done.data.items)
    notify(`Mod 索引完成，共 ${done.data.total} 个 zipmod`, 'ok')
    appendLog('ok', 'MOD', `增量索引完成：${done.data.total} 个 zipmod`)
  }

  const handlePickScene = async () => {
    const pickRes = await backend.pickCardFile('选择 Studio 场景卡 PNG')
    if (!pickRes.ok || !pickRes.data) return
    setAnalyzingScene(true)
    const res = await backend.analyzeScene(pickRes.data)
    setAnalyzingScene(false)
    if (!res.ok || !res.data) {
      notify(`场景卡解析失败：${res.error || '文件格式不匹配'}`, 'error')
      return
    }
    setSceneResult(res.data)
    notify(`场景解析完成：发现 ${res.data.characterCount} 名内嵌角色`, 'ok')
    appendLog('ok', 'SCENE', `分析场景卡：${res.data.fileName}`)
  }

  const handleExtractScene = async () => {
    if (!sceneResult) return
    const dirRes = await backend.pickDirectory('选择角色卡提取输出目录', config.output_dir)
    if (!dirRes.ok || !dirRes.data) return
    setExtractingScene(true)
    const res = await backend.extractSceneCharacters(sceneResult.path, dirRes.data)
    setExtractingScene(false)
    if (!res.ok || !res.data) {
      notify(`提取失败：${res.error}`, 'error')
      return
    }
    notify(`已无损提取 ${res.data.count} 张角色卡到 ${res.data.outDir}`, 'ok')
    appendLog('ok', 'SCENE', `从 ${sceneResult.fileName} 提取 ${res.data.count} 张角色卡`)
  }

  // ---- 自更新逻辑（阶段文案、进度条、重启未保存保护） ----
  const handleCheckUpdate = async () => {
    setUpdateState({
      ...INITIAL_UPDATE_STATE,
      stage: 'checking',
      stageText: '正在连接 GitHub 检查最新版本…',
      percent: 15,
    })
    const startRes = await backend.startCheckUpdate()
    if (!startRes.ok || !startRes.data) {
      setUpdateState((prev) => ({
        ...prev,
        stage: 'error',
        errorText: startRes.error || '无法启动检查更新',
      }))
      return
    }
    const done = await waitTask<{
      hasUpdate: boolean
      currentVersion: string
      release?: UpdateReleaseInfo
    }>(startRes.data.taskId, (st) => {
      setUpdateState((prev) => ({
        ...prev,
        stageText: st.message || prev.stageText,
        percent: st.percent,
      }))
    })
    if (!done.ok || !done.data) {
      setUpdateState((prev) => ({
        ...prev,
        stage: 'error',
        errorText: `检查更新失败：${done.error || '网络异常'}`,
      }))
      appendLog('error', 'UPDATE', `检查更新失败：${done.error}`)
      return
    }
    if (!done.data.hasUpdate || !done.data.release) {
      setUpdateState({
        ...INITIAL_UPDATE_STATE,
        stage: 'latest',
        stageText: `当前已是最新稳定版（${done.data.currentVersion}）`,
        percent: 100,
      })
      notify('当前已是最新版本', 'ok')
      return
    }
    setUpdateState({
      ...INITIAL_UPDATE_STATE,
      stage: 'available',
      stageText: `发现新版本 ${done.data.release.version}，可点击下载更新包`,
      release: done.data.release,
      totalBytes: done.data.release.size,
    })
    notify(`发现新版本 ${done.data.release.version}`, 'info')
  }

  const handleDownloadUpdate = async () => {
    setUpdateState((prev) => ({
      ...prev,
      stage: 'downloading',
      stageText: '正在下载新版本…',
      percent: 0,
      downloadedBytes: 0,
      errorText: '',
    }))
    const startRes = await backend.startDownloadUpdate()
    if (!startRes.ok || !startRes.data) {
      setUpdateState((prev) => ({
        ...prev,
        stage: 'error',
        errorText: startRes.error || '无法启动下载',
      }))
      return
    }
    const done = await waitTask<{ version: string; artifactPath: string; isFrozen: boolean }>(
      startRes.data.taskId,
      (st) => {
        setUpdateState((prev) => ({
          ...prev,
          stageText: st.message || '正在下载并校验…',
          percent: st.percent,
          downloadedBytes: st.current,
          totalBytes: st.total || prev.totalBytes,
        }))
      },
    )
    if (!done.ok || !done.data) {
      setUpdateState((prev) => ({
        ...prev,
        stage: 'error',
        errorText: `下载或校验失败：${done.error || '文件可能损坏'}`,
      }))
      appendLog('error', 'UPDATE', `下载更新失败：${done.error}`)
      return
    }
    setUpdateState((prev) => ({
      ...prev,
      stage: 'ready',
      percent: 100,
      artifactPath: done.data!.artifactPath,
      stageText: done.data!.isFrozen
        ? `新版本 ${done.data!.version} 已校验就绪，可重启替换`
        : `新版本 ${done.data!.version} 已下载并校验完成（源码模式不覆盖开发目录）`,
    }))
    notify(`新版本 ${done.data.version} 已准备就绪`, 'ok')
  }

  const handleApplyUpdate = () => {
    const doApply = async () => {
      const res = await backend.applyUpdateAndRestart()
      if (!res.ok) {
        notify(`启动更新失败：${res.error}`, 'error')
      }
    }
    // 严格遵守规则 #10896：重启更新前复用未保存改动保护
    if ((editorDirty && !editorCard?.isDemo) || (modalDirty && !modalCard?.isDemo)) {
      setConfirmDialog({
        title: '角色编辑器还有未保存改动',
        message: '继续重启更新将放弃当前编辑器里未保存的修改。\n建议先取消并保存角色卡，或确认放弃修改并立即更新重启。',
        confirmLabel: '放弃改动并重启更新',
        danger: true,
        onConfirm: () => void doApply(),
      })
      return
    }
    void doApply()
  }

  return (
    <>
      <AppShell
        activePage={activePage}
        onSelectPage={(nextPage) => {
          setStatusOverride(null)
          setActivePage(nextPage)
        }}
        theme={theme}
        onChangeTheme={(next) => {
          setTheme(next)
          appendLog('info', 'THEME', `切换视觉主题 -> ${next}`)
        }}
        wallpaperUrl={config.wallpaper_url}
        wallpaperEnabled={config.wallpaper_enabled}
        onToggleWallpaper={() => {
          if (!config.wallpaper_url) {
            setActivePage('settings')
            notify('尚未选择壁纸图片，已在外观设置页为你打开壁纸工坊', 'info')
            return
          }
          setConfig((prev) => ({ ...prev, wallpaper_enabled: !prev.wallpaper_enabled }))
        }}
        uiMode={config.ui_mode}
        onToggleUiMode={() =>
          setConfig((prev) => ({
            ...prev,
            ui_mode: prev.ui_mode === 'normal' ? 'advanced' : 'normal',
          }))
        }
        appVersion={config.app_version}
        statusText={statusText}
        toast={toast}
      >
        {activePage === 'browser' && (
          <BrowserPage
            cards={cards}
            browseDir={browseDir}
            scannedDir={scannedDir}
            quickDirs={config.quick_dirs || []}
            recursive={recursive}
            scanning={scanningCards}
            scanProgress={scanProgress}
            loadingPage={loadingPage}
            pageMeta={pageMeta}
            filters={browserFilters}
            isDemoMode={isDemoMode}
            onChangeBrowseDir={setBrowseDir}
            onSelectQuickDir={(dir) => {
              setBrowseDir(dir)
              void handleScanDir(dir)
            }}
            onToggleRecursive={handleToggleRecursive}
            onChangeFilters={handleBrowserFiltersChange}
            onLoadMore={handleLoadMoreCards}
            onPickDirectory={handlePickBrowseDir}
            onScan={() => void handleScanDir()}
            onCancelScan={() => void handleCancelScan()}
            onLoadDemo={() => {
              if (activeScanTaskId.current) {
                const tid = activeScanTaskId.current
                activeScanTaskId.current = null
                void cancelAndReleaseTask(tid)
              }
              scanSeqRef.current += 1
              querySeqRef.current += 1
              setScanningCards(false)
              setScanProgress(null)
              setLoadingPage(false)
              setCards(DEMO_CARDS)
              setIsDemoMode(true)
              setBrowserFilters({ type: 'all', game: 'all', author: 'all', search: '' })
              setPageMeta({
                total: DEMO_CARDS.length,
                hasMore: false,
                indexed: true,
                complete: true,
                versionCounts: [],
              })
              notify('已载入内置日系示范画廊', 'info')
            }}
            onQuickEditCard={(card) => void handleQuickEditCard(card)}
            onInspectScene={(card) => void handleInspectSceneFromGallery(card)}
            onTagsSaved={(path, tags) =>
              setCards((prev) => prev.map((c) => (c.path === path ? { ...c, tags } : c)))
            }
            onAuthorSaved={(path, author, authorSource, authorHistory) =>
              setCards((prev) =>
                prev.map((c) =>
                  c.path === path ? { ...c, author, authorSource, authorHistory } : c,
                ),
              )
            }
            onCardConverted={() => {
              if (scannedDir.trim() && !isDemoMode) {
                void handleScanDir(scannedDir)
              }
            }}
            onRevealFile={(p) => void backend.revealInExplorer(p)}
            onNotify={notify}
            onLog={appendLog}
          />
        )}

        {activePage === 'editor' && (
          <EditorPage
            card={editorCard}
            coverPreviewUrl={pendingCoverUrl}
            dirty={editorDirty}
            saving={savingCard}
            modCheck={editorModCheck}
            checkingMods={checkingEditorMods}
            onPickCardFile={() => void handlePickCardFile()}
            onPickCover={() => void handlePickCover()}
            onUpdateParam={handleUpdateParam}
            onSaveAs={() => handleSaveCard(false)}
            onSaveOverwrite={() => handleSaveCard(true)}
            onReset={() => {
              if (editorOriginal) {
                setEditorCard(structuredClone(editorOriginal))
                setPendingCoverPath('')
                setPendingCoverUrl('')
                setEditorDirty(false)
                notify('已还原未保存改动', 'info')
              }
            }}
            onCopyModIds={() => {
              if (!editorCard) return
              void navigator.clipboard?.writeText(editorCard.modIds.join('\n'))
              notify(`已复制 ${editorCard.modIds.length} 条 Mod GUID`, 'ok')
            }}
            onCheckCardMods={() => void handleCheckEditorMods()}
            onCardConverted={() => {
              if (scannedDir.trim() && !isDemoMode) {
                void handleScanDir(scannedDir)
              }
            }}
            onNotify={notify}
            onLog={appendLog}
          />
        )}

        {activePage === 'pack' && (
          <PackPage
            defaultOutDir={config.pack_out_dir || config.output_dir}
            uiMode={config.ui_mode}
            onNotify={notify}
            onLog={appendLog}
          />
        )}

        {activePage === 'share' && (
          <SharePage
            defaultOutDir={config.output_dir}
            onNotify={notify}
            onLog={appendLog}
          />
        )}

        {activePage === 'mod' && (
          <ModPage
            mods={mods}
            scanning={scanningMods}
            scanProgress={modScanProgress}
            modDirs={[
              ...(config.kk_game_dir ? [`${config.kk_game_dir}/mods`] : []),
              ...(config.kks_game_dir ? [`${config.kks_game_dir}/mods`] : []),
              ...config.mod_dirs,
            ]}
            onScanMods={() => void handleScanMods()}
            onNotify={notify}
            onLog={appendLog}
          />
        )}

        {activePage === 'scene' && (
          <ScenePage
            scene={sceneResult}
            analyzing={analyzingScene}
            extracting={extractingScene}
            onPickScene={() => void handlePickScene()}
            onExtractCharacters={() => void handleExtractScene()}
            onNotify={notify}
            onLog={appendLog}
          />
        )}

        {activePage === 'log' && (
          <LogPage
            logs={logs}
            onClear={() => {
              setLogs([])
              notify('已清空日志视图', 'info')
            }}
          />
        )}

        {activePage === 'settings' && (
          <SettingsPage
            config={config}
            theme={theme}
            saving={savingConfig}
            updateInfo={updateInfo}
            updateState={updateState}
            onChangeTheme={setTheme}
            onUpdateConfig={(patch) => setConfig((prev) => ({ ...prev, ...patch }))}
            onPickDirectory={async (field, label) => {
              const res = await backend.pickDirectory(`选择${label}`, config[field])
              if (res.ok && res.data) {
                setConfig((prev) => ({ ...prev, [field]: res.data! }))
              }
            }}
            onPickWallpaper={() => void handlePickWallpaper()}
            onClearWallpaper={() =>
              setConfig((prev) => ({
                ...prev,
                wallpaper_path: '',
                wallpaper_url: '',
                wallpaper_enabled: false,
              }))
            }
            onSaveConfig={() => void handleSaveConfig()}
            onCheckUpdate={() => void handleCheckUpdate()}
            onDownloadUpdate={() => void handleDownloadUpdate()}
            onApplyUpdate={handleApplyUpdate}
            onOpenReleasePage={(u) => void backend.openExternalUrl(u)}
            onRevealArtifact={(p) => void backend.revealInExplorer(p)}
          />
        )}
      </AppShell>

      <CardEditorModal
        card={modalCard}
        coverPreviewUrl={modalCoverUrl}
        dirty={modalDirty}
        saving={modalSaving}
        modCheck={modalModCheck}
        checkingMods={modalCheckingMods}
        onRequestClose={handleRequestCloseModal}
        onExpandToPage={handleExpandModalToPage}
        onPickCover={async () => {
          const res = await backend.pickImageFile('选择新封面图片 (PNG)')
          if (!res.ok || !res.data) return
          const urlRes = await backend.getWallpaperDataUrl(res.data)
          if (urlRes.ok && urlRes.data) {
            setModalCoverPath(res.data)
            setModalCoverUrl(urlRes.data)
            setModalDirty(true)
            notify('已选定新封面，保存角色卡时生效', 'info')
          }
        }}
        onUpdateParam={(updater) => {
          setModalCard((prev) => (prev ? { ...prev, parameter: updater(prev.parameter) } : prev))
          setModalDirty(true)
        }}
        onSaveAs={() => handleSaveModalCard(false)}
        onSaveOverwrite={() => handleSaveModalCard(true)}
        onReset={() => {
          if (modalOriginal) {
            setModalCard(structuredClone(modalOriginal))
            setModalCoverPath('')
            setModalCoverUrl('')
            setModalDirty(false)
            notify('已还原未保存改动', 'info')
          }
        }}
        onCopyModIds={() => {
          if (!modalCard) return
          void navigator.clipboard?.writeText(modalCard.modIds.join('\n'))
          notify(`已复制 ${modalCard.modIds.length} 条 Mod GUID`, 'ok')
        }}
        onCheckCardMods={async () => {
          if (!modalCard || modalCard.isDemo) return
          setModalCheckingMods(true)
          const res = await backend.checkCardMods(modalCard.path)
          setModalCheckingMods(false)
          if (!res.ok || !res.data) {
            notify(`缺失检测失败：${res.error}`, 'error')
            return
          }
          setModalModCheck(res.data)
          notify(
            `检测完成：已装 ${res.data.present.length} 项，缺失 ${res.data.missing.length} 项`,
            res.data.missing.length > 0 ? 'warn' : 'ok',
          )
        }}
        onCardConverted={() => {
          if (scannedDir.trim() && !isDemoMode) {
            void handleScanDir(scannedDir)
          }
        }}
        onNotify={notify}
        onLog={appendLog}
      />

      <ConfirmModal dialog={confirmDialog} onClose={() => setConfirmDialog(null)} />
    </>
  )
}
export default App
