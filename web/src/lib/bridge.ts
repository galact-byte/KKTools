import type {
  AppConfig,
  CardDetail,
  CardModCheckResult,
  CardSummary,
  ModSummaryItem,
  SceneAnalysisResult,
  TaskState,
  UpdateInfo,
} from '../types/kk'

declare global {
  interface Window {
    pywebview?: {
      api: Record<string, (...args: unknown[]) => Promise<unknown>>
    }
  }
}

export interface BridgeResult<T> {
  ok: boolean
  data?: T
  error?: string
}

async function callBackend<T>(method: string, ...args: unknown[]): Promise<BridgeResult<T>> {
  if (typeof window !== 'undefined' && window.pywebview?.api?.[method]) {
    try {
      const res = (await window.pywebview.api[method](...args)) as BridgeResult<T>
      return res
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : String(err) }
    }
  }

  try {
    const resp = await fetch(`/api/${method}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ args }),
    })
    if (!resp.ok) {
      return { ok: false, error: `HTTP ${resp.status}` }
    }
    return (await resp.json()) as BridgeResult<T>
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}

export async function waitTask<T>(
  taskId: string,
  onProgress?: (state: TaskState<T>) => void,
  intervalMs = 220,
): Promise<BridgeResult<T>> {
  while (true) {
    const res = await callBackend<TaskState<T>>('poll_task', taskId)
    if (!res.ok || !res.data) {
      return { ok: false, error: res.error || '轮询任务失败' }
    }
    const state = res.data
    onProgress?.(state)
    if (state.status === 'done') {
      return { ok: true, data: state.result }
    }
    if (state.status === 'error') {
      return { ok: false, error: state.error || '后台任务执行失败' }
    }
    await new Promise((r) => window.setTimeout(r, intervalMs))
  }
}

export interface ImportPlan {
  files: { source: string; target: string; game: string; type: string }[]
  skipped: { source: string; reason: string }[]
}

export const backend = {
  getCardTags: (path: string) => callBackend<string[]>('get_card_tags', path),
  setCardTags: (path: string, tags: string[]) => callBackend<string[]>('set_card_tags', path, tags),
  startExportData: (opts: { kind: 'list' | 'character' | 'scene'; paths: string[]; outDir: string; format: 'csv' | 'json' | 'txt' }) => callBackend<{ taskId: string }>('start_export_data', opts),
  previewAutoImport: (path: string, game: string) => callBackend<ImportPlan>('preview_auto_import', path, game),
  startAutoImport: (path: string, game: string) => callBackend<{ taskId: string }>('start_auto_import', path, game),
  startRecovery: (opts: { path: string; sidecar: string; outDir: string; repair: boolean }) => callBackend<{ taskId: string }>('start_recovery', opts),
  recordLog: (level: string, source: string, message: string) => callBackend<void>('record_log', level, source, message),
  openLogDirectory: () => callBackend<string>('open_log_directory'),
  exportManifest: (path: string) => callBackend<{ count: number }>('export_manifest', path),
  compareManifest: (path: string) => callBackend<{ both: number; mine_only: string[]; theirs_only: string[] }>('compare_manifest', path),
  startExportModList: (path: string, outDir: string) => callBackend<{ taskId: string }>('start_export_mod_list', path, outDir),
  setDirtyState: (dirty: boolean) => callBackend<boolean>('set_dirty_state', dirty),
  getConfig: () => callBackend<AppConfig>('get_config'),
  saveConfig: (patch: Partial<AppConfig>) => callBackend<AppConfig>('save_config', patch),
  pickDirectory: (title: string, initialDir = '') =>
    callBackend<string>('pick_directory', title, initialDir),
  pickImageFile: (title: string) => callBackend<string>('pick_image_file', title),
  pickCardFile: (title: string) => callBackend<string>('pick_card_file', title),
  pickCardFiles: (title: string) => callBackend<string[]>('pick_card_files', title),
  pickAnyFiles: (title: string, multiple = true) =>
    callBackend<string[] | string>('pick_any_files', title, multiple),
  pickSaveTxt: (title: string) => callBackend<string>('pick_save_txt', title),
  revealInExplorer: (path: string) => callBackend<boolean>('reveal_in_explorer', path),
  openExternalUrl: (url: string) => callBackend<boolean>('open_external_url', url),

  // 浏览与卡片编辑
  scanDirectory: (directory: string, recursive: boolean) =>
    callBackend<CardSummary[]>('scan_directory', directory, recursive),
  inspectFile: (path: string) =>
    callBackend<{ path: string; type: string; game: string; name: string }>('inspect_file', path),
  loadCard: (path: string) => callBackend<CardDetail>('load_card', path),
  saveCard: (payload: {
    path: string
    overwrite: boolean
    parameter: CardDetail['parameter']
    coverPath?: string
  }) => callBackend<{ savedPath: string; warning?: string }>('save_card', payload),

  // 打包与解包
  startPack: (opts: {
    independent?: boolean
    sources: string[]
    outDir: string
    archiveName: string
    stegoMode: 'none' | 'image' | 'video'
    carrierPath?: string
    passwords?: string[]
    splitMB?: number
    writeRecovery?: boolean
  }) => callBackend<{ taskId: string }>('start_pack', opts),
  startUnpack: (opts: { inputPath: string; outDir: string; passwords?: string[] }) =>
    callBackend<{ taskId: string }>('start_unpack', opts),

  // 分享与整理
  startShareExport: (opts: {
    cardPaths: string[]
    outDir: string
    groupByChar?: boolean
    excludeGuids?: string
  }) => callBackend<{ taskId: string }>('start_share_export', opts),
  startShareImport: (opts: { pkgDir: string; cardTarget: string; modTarget?: string }) =>
    callBackend<{ taskId: string }>('start_share_import', opts),
  startOrganizeCards: (opts: { srcDir: string; outDir: string; by: string; move: boolean }) =>
    callBackend<{ taskId: string }>('start_organize_cards', opts),

  // Mod 仓库
  getCachedMods: () => callBackend<{ total: number; items: ModSummaryItem[] }>('get_cached_mods'),
  startScanMods: (dirs?: string[]) => callBackend<{ taskId: string }>('start_scan_mods', dirs),
  checkCardMods: (cardPath: string) => callBackend<CardModCheckResult>('check_card_mods', cardPath),
  exportModGuids: (outPath: string) =>
    callBackend<{ count: number; path: string }>('export_mod_guids', outPath),
  startArchiveUnreferenced: (opts: { cardDir: string; archiveDir: string; move: boolean }) =>
    callBackend<{ taskId: string }>('start_archive_unreferenced', opts),
  startOrganizeMods: (opts: { targetDir: string; move: boolean }) =>
    callBackend<{ taskId: string }>('start_organize_mods', opts),

  // 场景卡
  analyzeScene: (path: string) => callBackend<SceneAnalysisResult>('analyze_scene', path),
  extractSceneCharacters: (scenePath: string, outDir: string) =>
    callBackend<{ count: number; saved: string[]; outDir: string }>(
      'extract_scene_characters',
      scenePath,
      outDir,
    ),

  // 壁纸与更新
  getWallpaperDataUrl: (path: string) => callBackend<string>('get_wallpaper_data_url', path),
  getUpdateInfo: () => callBackend<UpdateInfo>('get_update_info'),
  startCheckUpdate: () => callBackend<{ taskId: string }>('start_check_update'),
  startDownloadUpdate: () => callBackend<{ taskId: string }>('start_download_update'),
  applyUpdateAndRestart: () =>
    callBackend<{ restarting: boolean; plan: string }>('apply_update_and_restart'),
  cleanupPendingUpdate: () => callBackend<boolean>('cleanup_pending_update'),
}
