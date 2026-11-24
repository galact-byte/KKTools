export type ThemeId = 'sora_light' | 'washi_light' | 'tsukiyo_dark' | 'yorha_light'

export type PageId =
  | 'browser'
  | 'editor'
  | 'pack'
  | 'share'
  | 'mod'
  | 'scene'
  | 'log'
  | 'settings'

export type CardType = 'character' | 'coordinate' | 'scene' | 'other'

export interface TaskState<T = unknown> {
  id: string
  status: 'running' | 'done' | 'error'
  current: number
  total: number
  percent: number
  message: string
  result?: T
  error?: string
}

export interface CardSummary {
  id: string
  path: string
  fileName: string
  type: CardType
  game: string
  name: string
  thumbnailUrl: string
  tags?: string[]
  isDemo?: boolean
  subtitle?: string
  personalityLabel?: string
  bloodType?: string
  birthday?: string
  modCount?: number
  fileSizeText?: string
}

export interface CardDetail {
  path: string
  fileName: string
  game: string
  gameName: string
  marker: string
  version: string
  thumbnailUrl: string
  faceUrl?: string
  isDemo?: boolean
  parameter: {
    lastname: string
    firstname: string
    nickname: string
    sex: number
    personality: number | string
    bloodType: number | string
    birthMonth: number
    birthDay: number
    clubActivities: number | string
    voiceRate?: number
    awnser: Record<string, boolean>
    attribute: Record<string, boolean>
    denial: Record<string, boolean>
    rawScalars: Record<string, string | number | boolean>
  }
  modIds: string[]
  blockNames: string[]
}

export interface AppConfig {
  kk_game_dir: string
  kks_game_dir: string
  mod_dirs: string[]
  output_dir: string
  last_browse_dir: string
  carrier_dir: string
  pack_out_dir?: string
  quick_dirs?: Array<{ game: string; label: string; path: string }>
  theme: string
  wallpaper_path: string
  wallpaper_url: string
  wallpaper_enabled: boolean
  wallpaper_overlay: number
  wallpaper_panel_alpha: number
  wallpaper_blur: number
  ui_mode: 'normal' | 'advanced'
  start_page: number
  recent_cards: string[]
  app_version: string
  is_frozen?: boolean
}

export interface ModSummaryItem {
  guid: string
  name: string
  version: string
  author: string
  fileName: string
  path: string
  sizeMB: number
}

export interface CardModCheckResult {
  cardPath: string
  total: number
  present: string[]
  missing: string[]
}

export interface LogEntry {
  id: string
  time: string
  level: 'info' | 'ok' | 'warn' | 'error'
  source: string
  message: string
}

export interface SceneAnalysisResult {
  path: string
  fileName: string
  previewUrl: string
  characterCount: number
  characters: Array<{ index: number; name: string; game: string; previewUrl: string }>
  modIds: string[]
}

export interface UpdateReleaseInfo {
  version: string
  notes: string
  pageUrl: string
  size: number
  hasSha256: boolean
}

export interface UpdateInfo {
  currentVersion: string
  isFrozen: boolean
  releasesUrl: string
  lastResult: Record<string, unknown> | null
  hasPendingArtifact: boolean
}
