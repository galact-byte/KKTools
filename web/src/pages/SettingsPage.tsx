import React from 'react'
import {
  ArrowUpCircle,
  Check,
  Download,
  ExternalLink,
  FolderOpen,
  Image as ImageIcon,
  Palette,
  RefreshCw,
  RotateCw,
  Save,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { THEMES } from '../data/constants'
import type { AppConfig, ThemeId, UpdateInfo, UpdateReleaseInfo } from '../types/kk'

export interface UpdateUiState {
  stage: 'idle' | 'checking' | 'available' | 'latest' | 'downloading' | 'ready' | 'error'
  stageText: string
  percent: number
  downloadedBytes: number
  totalBytes: number
  release: UpdateReleaseInfo | null
  artifactPath: string
  errorText: string
}

interface SettingsPageProps {
  config: AppConfig
  theme: ThemeId
  saving: boolean
  updateInfo: UpdateInfo | null
  updateState: UpdateUiState
  onChangeTheme: (theme: ThemeId) => void
  onUpdateConfig: (patch: Partial<AppConfig>) => void
  onPickDirectory: (
    field: 'kk_game_dir' | 'kks_game_dir' | 'output_dir' | 'carrier_dir',
    label: string,
  ) => void
  onPickWallpaper: () => void
  onClearWallpaper: () => void
  onSaveConfig: () => void
  onCheckUpdate: () => void
  onDownloadUpdate: () => void
  onApplyUpdate: () => void
  onOpenReleasePage: (url: string) => void
  onRevealArtifact: (path: string) => void
}

function fmtBytes(n: number): string {
  if (!n || n <= 0) return '0 B'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(2)} MB`
}

export const SettingsPage: React.FC<SettingsPageProps> = ({
  config,
  theme,
  saving,
  updateInfo,
  updateState,
  onChangeTheme,
  onUpdateConfig,
  onPickDirectory,
  onPickWallpaper,
  onClearWallpaper,
  onSaveConfig,
  onCheckUpdate,
  onDownloadUpdate,
  onApplyUpdate,
  onOpenReleasePage,
  onRevealArtifact,
}) => {
  const isBusyUpdate = updateState.stage === 'checking' || updateState.stage === 'downloading'
  const isFrozen = Boolean(updateInfo?.isFrozen ?? config.is_frozen)

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto px-5 py-4">
        <div className="mx-auto flex max-w-[960px] flex-col gap-4 pb-6">
          {/* 1. 视觉主题陈列馆 */}
          <section className="kk-surface flex flex-col gap-4 p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Palette size={16} style={{ color: 'var(--primary)' }} />
                <h2 className="text-[15px] font-bold" style={{ color: 'var(--text-strong)' }}>
                  界面气质与主题
                </h2>
              </div>
              <span className="text-[12px]" style={{ color: 'var(--text-dim)' }}>
                四套主题统一柔和圆角系统，点击实时平滑切换
              </span>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {THEMES.map((item) => {
                const active = item.id === theme
                const [bg, surface, primary, accent] = item.swatches
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onChangeTheme(item.id)}
                    className="group flex flex-col overflow-hidden rounded-[var(--radius-md)] text-left transition-all cursor-pointer"
                    style={{
                      backgroundColor: 'var(--surface-alt)',
                      border: `1.5px solid ${active ? 'var(--primary)' : 'var(--border)'}`,
                      boxShadow: active ? '0 0 0 3px var(--primary-soft)' : 'none',
                    }}
                  >
                    <div
                      className="relative flex h-24 w-full gap-1.5 p-2.5"
                      style={{ backgroundColor: bg }}
                    >
                      <div
                        className="flex w-7 flex-col gap-1 rounded-[5px] p-1"
                        style={{ backgroundColor: surface, opacity: 0.92 }}
                      >
                        <div className="h-2.5 w-2.5 rounded-[3px]" style={{ backgroundColor: primary }} />
                        <div
                          className="mt-1 h-1.5 w-full rounded-full"
                          style={{ backgroundColor: primary, opacity: 0.35 }}
                        />
                        <div
                          className="h-1.5 w-3/4 rounded-full"
                          style={{ backgroundColor: primary, opacity: 0.2 }}
                        />
                      </div>
                      <div className="flex flex-1 flex-col gap-1.5">
                        <div
                          className="flex h-4 items-center justify-between rounded-[4px] px-1.5"
                          style={{ backgroundColor: surface }}
                        >
                          <span
                            className="h-1.5 w-10 rounded-full"
                            style={{ backgroundColor: primary, opacity: 0.7 }}
                          />
                          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: accent }} />
                        </div>
                        <div className="grid flex-1 grid-cols-3 gap-1.5">
                          {[0, 1, 2].map((k) => (
                            <div
                              key={k}
                              className="flex flex-col justify-end rounded-[4px] p-1"
                              style={{ backgroundColor: surface }}
                            >
                              <div
                                className="h-1.5 w-3/4 rounded-full"
                                style={{
                                  backgroundColor: k === 1 ? accent : primary,
                                  opacity: 0.55,
                                }}
                              />
                            </div>
                          ))}
                        </div>
                      </div>
                      {active && (
                        <span
                          className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full"
                          style={{ backgroundColor: primary, color: '#ffffff' }}
                        >
                          <Check size={12} strokeWidth={2.8} />
                        </span>
                      )}
                    </div>

                    <div className="flex flex-col gap-1 p-3">
                      <div className="flex items-center justify-between">
                        <span
                          className="text-[13.5px] font-bold"
                          style={{ color: 'var(--text-strong)' }}
                        >
                          {item.name}
                        </span>
                        <span
                          className="font-mono-num text-[10px]"
                          style={{ color: 'var(--text-dim)' }}
                        >
                          {item.variant === 'dark' ? 'DARK' : 'LIGHT'}
                        </span>
                      </div>
                      <p
                        className="text-[11.5px] leading-relaxed"
                        style={{ color: 'var(--text-muted)' }}
                      >
                        {item.desc}
                      </p>
                    </div>
                  </button>
                )
              })}
            </div>
          </section>

          {/* 2. 壁纸与毛玻璃通透工坊 */}
          <section className="kk-surface flex flex-col gap-4 p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ImageIcon size={16} style={{ color: 'var(--sakura)' }} />
                <h2 className="text-[15px] font-bold" style={{ color: 'var(--text-strong)' }}>
                  壁纸与毛玻璃融合
                </h2>
              </div>
              <label
                className="flex cursor-pointer items-center gap-2 text-[13px] font-medium"
                style={{ color: 'var(--text-strong)' }}
              >
                <input
                  type="checkbox"
                  checked={config.wallpaper_enabled}
                  onChange={(e) => onUpdateConfig({ wallpaper_enabled: e.target.checked })}
                  className="h-4 w-4 accent-[var(--primary)]"
                />
                <span>启用壁纸背景</span>
              </label>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-[240px_1fr]">
              <div
                className="relative flex h-36 flex-col items-center justify-center overflow-hidden rounded-[var(--radius-md)] border"
                style={{
                  borderColor: 'var(--border)',
                  backgroundColor: 'var(--surface-alt)',
                }}
              >
                {config.wallpaper_url ? (
                  <>
                    <img
                      src={config.wallpaper_url}
                      alt="当前壁纸预览"
                      className="h-full w-full object-cover"
                    />
                    <span
                      className="absolute bottom-2 left-2 rounded-full px-2 py-0.5 text-[10.5px] font-medium backdrop-blur-md"
                      style={{ backgroundColor: 'rgba(15, 25, 45, 0.72)', color: '#ffffff' }}
                    >
                      当前生效壁纸
                    </span>
                  </>
                ) : (
                  <div
                    className="flex flex-col items-center gap-1.5 text-[12px]"
                    style={{ color: 'var(--text-dim)' }}
                  >
                    <ImageIcon size={20} />
                    <span>未设置自定义壁纸</span>
                  </div>
                )}
              </div>

              <div className="flex flex-col justify-between gap-3">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    readOnly
                    value={config.wallpaper_path || '尚未选择壁纸图片'}
                    className="kk-input flex-1 text-[12px]"
                  />
                  <button type="button" onClick={onPickWallpaper} className="kk-btn">
                    <FolderOpen size={14} />
                    <span>选择图片</span>
                  </button>
                  {config.wallpaper_path && (
                    <button
                      type="button"
                      onClick={onClearWallpaper}
                      className="kk-btn kk-btn-danger px-2.5"
                      title="清除壁纸"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
                  <label className="kk-surface-alt flex flex-col gap-1.5 p-2.5">
                    <div className="flex items-center justify-between text-[12px]">
                      <span style={{ color: 'var(--text-muted)' }}>柔光遮罩浓度</span>
                      <span className="font-mono-num font-semibold" style={{ color: 'var(--primary)' }}>
                        {config.wallpaper_overlay}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={90}
                      value={config.wallpaper_overlay}
                      onChange={(e) =>
                        onUpdateConfig({ wallpaper_overlay: Number(e.target.value) })
                      }
                      className="w-full accent-[var(--primary)]"
                    />
                  </label>

                  <label className="kk-surface-alt flex flex-col gap-1.5 p-2.5">
                    <div className="flex items-center justify-between text-[12px]">
                      <span style={{ color: 'var(--text-muted)' }}>面板不透明度</span>
                      <span className="font-mono-num font-semibold" style={{ color: 'var(--primary)' }}>
                        {config.wallpaper_panel_alpha}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min={45}
                      max={100}
                      value={config.wallpaper_panel_alpha}
                      onChange={(e) =>
                        onUpdateConfig({ wallpaper_panel_alpha: Number(e.target.value) })
                      }
                      className="w-full accent-[var(--primary)]"
                    />
                  </label>

                  <label className="kk-surface-alt flex flex-col gap-1.5 p-2.5">
                    <div className="flex items-center justify-between text-[12px]">
                      <span style={{ color: 'var(--text-muted)' }}>毛玻璃模糊度</span>
                      <span className="font-mono-num font-semibold" style={{ color: 'var(--primary)' }}>
                        {config.wallpaper_blur}px
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={28}
                      value={config.wallpaper_blur}
                      onChange={(e) => onUpdateConfig({ wallpaper_blur: Number(e.target.value) })}
                      className="w-full accent-[var(--primary)]"
                    />
                  </label>
                </div>
              </div>
            </div>
          </section>

          {/* 3. 版本与软件更新 */}
          <section className="kk-surface flex flex-col gap-3.5 p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <ArrowUpCircle size={16} style={{ color: 'var(--primary)' }} />
                <h2 className="text-[15px] font-bold" style={{ color: 'var(--text-strong)' }}>
                  版本与更新
                </h2>
                <span
                  className="font-mono-num rounded-full px-2 py-0.5 text-[11px] font-semibold"
                  style={{ backgroundColor: 'var(--primary-soft)', color: 'var(--primary)' }}
                >
                  {updateInfo?.currentVersion || config.app_version}
                </span>
                <span className="text-[11.5px]" style={{ color: 'var(--text-dim)' }}>
                  {isFrozen ? '便携单文件版（支持原位替换重启）' : '源码运行模式（仅检查与下载）'}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={isBusyUpdate}
                  onClick={onCheckUpdate}
                  className="kk-btn"
                >
                  <RefreshCw
                    size={13}
                    className={updateState.stage === 'checking' ? 'animate-spin' : ''}
                  />
                  <span>{updateState.stage === 'checking' ? '检查中…' : '检查更新'}</span>
                </button>
                {updateState.stage === 'available' && updateState.release && (
                  <button
                    type="button"
                    onClick={onDownloadUpdate}
                    className="kk-btn kk-btn-primary"
                  >
                    <Download size={13} />
                    <span>下载 {updateState.release.version}</span>
                  </button>
                )}
                {updateState.stage === 'ready' && isFrozen && (
                  <button
                    type="button"
                    onClick={onApplyUpdate}
                    className="kk-btn kk-btn-primary"
                  >
                    <RotateCw size={13} />
                    <span>重启并替换更新</span>
                  </button>
                )}
                {updateState.stage === 'ready' && !isFrozen && updateState.artifactPath && (
                  <button
                    type="button"
                    onClick={() => onRevealArtifact(updateState.artifactPath)}
                    className="kk-btn kk-btn-primary"
                  >
                    <FolderOpen size={13} />
                    <span>打开已下载文件</span>
                  </button>
                )}
                {updateInfo?.releasesUrl && (
                  <button
                    type="button"
                    onClick={() => onOpenReleasePage(updateInfo.releasesUrl)}
                    className="kk-btn-ghost inline-flex items-center gap-1 rounded-[var(--radius-sm)] px-2.5 py-1.5 text-[12px] cursor-pointer"
                  >
                    <ExternalLink size={13} />
                    <span>发布页</span>
                  </button>
                )}
              </div>
            </div>

            {/* 阶段文案与下载进度条 */}
            {(updateState.stage !== 'idle' || updateState.stageText) && (
              <div className="kk-surface-alt flex flex-col gap-2 p-3 text-[12.5px]">
                <div className="flex items-center justify-between gap-2">
                  <span
                    style={{
                      color:
                        updateState.stage === 'error'
                          ? 'var(--danger)'
                          : updateState.stage === 'ready' || updateState.stage === 'latest'
                            ? 'var(--success)'
                            : 'var(--text-strong)',
                    }}
                  >
                    {updateState.stage === 'error'
                      ? updateState.errorText || '检查或下载更新失败'
                      : updateState.stageText}
                  </span>
                  {updateState.stage === 'downloading' && (
                    <span className="font-mono-num shrink-0 font-semibold" style={{ color: 'var(--primary)' }}>
                      {updateState.percent}% · {fmtBytes(updateState.downloadedBytes)} /{' '}
                      {fmtBytes(updateState.totalBytes)}
                    </span>
                  )}
                </div>
                {(updateState.stage === 'downloading' || updateState.stage === 'checking') && (
                  <div className="kk-progress-bar">
                    <div
                      className="kk-progress-fill"
                      style={{ width: `${Math.max(4, updateState.percent)}%` }}
                    />
                  </div>
                )}
                {updateState.release?.notes &&
                  (updateState.stage === 'available' || updateState.stage === 'ready') && (
                    <pre
                      className="mt-1 max-h-32 overflow-y-auto whitespace-pre-wrap rounded-[var(--radius-sm)] p-2.5 text-[12px] leading-relaxed"
                      style={{
                        backgroundColor: 'var(--surface)',
                        border: '1px solid var(--border)',
                        color: 'var(--text)',
                      }}
                    >
                      {updateState.release.notes}
                    </pre>
                  )}
              </div>
            )}
          </section>

          {/* 4. 游戏与常用目录 */}
          <section className="kk-surface flex flex-col gap-3.5 p-5">
            <div className="flex items-center gap-2">
              <Sparkles size={16} style={{ color: 'var(--primary)' }} />
              <h2 className="text-[15px] font-bold" style={{ color: 'var(--text-strong)' }}>
                游戏目录与工作路径
              </h2>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {(
                [
                  { key: 'kk_game_dir', label: '恋活 (KK) 游戏根目录' },
                  { key: 'kks_game_dir', label: '恋活日光浴 (KKS) 根目录' },
                  { key: 'output_dir', label: '默认导出输出目录' },
                  { key: 'carrier_dir', label: '伪装载体默认目录' },
                ] as const
              ).map(({ key, label }) => (
                <div key={key} className="flex flex-col gap-1.5">
                  <span className="text-[12px] font-medium" style={{ color: 'var(--text-muted)' }}>
                    {label}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <input
                      type="text"
                      value={config[key]}
                      onChange={(e) => onUpdateConfig({ [key]: e.target.value })}
                      placeholder="未配置"
                      className="kk-input flex-1 text-[12.5px]"
                    />
                    <button
                      type="button"
                      onClick={() => onPickDirectory(key, label)}
                      className="kk-btn px-2.5"
                      title={`选择${label}`}
                    >
                      <FolderOpen size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>

      {/* 底部常驻保存条 */}
      <div
        className="kk-topbar flex shrink-0 items-center justify-between px-6 py-3"
        style={{ borderTop: '1px solid var(--border)', borderBottom: 'none' }}
      >
        <span className="text-[12.5px]" style={{ color: 'var(--text-muted)' }}>
          当前预览即时生效；点击右侧按钮将外观与目录配置写入{' '}
          <code className="font-mono-num">config.json</code>
        </span>
        <button
          type="button"
          disabled={saving}
          onClick={onSaveConfig}
          className="kk-btn kk-btn-primary"
        >
          <Save size={14} />
          <span>{saving ? '保存中…' : '保存全部设置'}</span>
        </button>
      </div>
    </div>
  )
}
