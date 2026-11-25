import React, { useState } from 'react'
import {
  Archive,
  Check,
  Clapperboard,
  FilePenLine,
  Image as ImageIcon,
  Layers,
  LayoutGrid,
  Palette,
  PanelLeftClose,
  PanelLeftOpen,
  ScrollText,
  Settings,
  Share2,
  SlidersHorizontal,
} from 'lucide-react'
import { THEMES } from '../data/constants'
import type { PageId, ThemeId } from '../types/kk'

interface NavItem {
  id: PageId
  label: string
  en: string
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>
  group: 'studio' | 'manage' | 'system'
}

export const NAV_ITEMS: NavItem[] = [
  { id: 'browser', label: '卡片画廊', en: 'GALLERY', icon: LayoutGrid, group: 'studio' },
  { id: 'editor', label: '角色编辑', en: 'CHARACTER', icon: FilePenLine, group: 'studio' },
  { id: 'scene', label: '场景卡工具', en: 'SCENE', icon: Clapperboard, group: 'studio' },
  { id: 'pack', label: '解包与打包', en: 'PACKING', icon: Archive, group: 'manage' },
  { id: 'share', label: '分享与整理', en: 'SHARE KIT', icon: Share2, group: 'manage' },
  { id: 'mod', label: 'Mod 仓库', en: 'MOD INDEX', icon: Layers, group: 'manage' },
  { id: 'log', label: '运行日志', en: 'LOGS', icon: ScrollText, group: 'system' },
  { id: 'settings', label: '外观与设置', en: 'SETTINGS', icon: Settings, group: 'system' },
]

interface AppShellProps {
  activePage: PageId
  onSelectPage: (page: PageId) => void
  theme: ThemeId
  onChangeTheme: (theme: ThemeId) => void
  wallpaperUrl: string
  wallpaperEnabled: boolean
  onToggleWallpaper: () => void
  uiMode: 'normal' | 'advanced'
  onToggleUiMode: () => void
  appVersion: string
  statusText: string
  toast: { text: string; tone: 'info' | 'ok' | 'warn' | 'error' } | null
  children: React.ReactNode
}

export const AppShell: React.FC<AppShellProps> = ({
  activePage,
  onSelectPage,
  theme,
  onChangeTheme,
  wallpaperUrl,
  wallpaperEnabled,
  onToggleWallpaper,
  uiMode,
  onToggleUiMode,
  appVersion,
  statusText,
  toast,
  children,
}) => {
  const [collapsed, setCollapsed] = useState(false)
  const [themeMenuOpen, setThemeMenuOpen] = useState(false)

  const currentNav = NAV_ITEMS.find((n) => n.id === activePage) ?? NAV_ITEMS[0]
  const currentThemeMeta = THEMES.find((t) => t.id === theme) ?? THEMES[0]
  const showWallpaper = Boolean(wallpaperEnabled && wallpaperUrl)

  const renderGroup = (group: NavItem['group'], title: string, showCollapsedDivider = false) => {
    const items = NAV_ITEMS.filter((n) => n.group === group)
    return (
      <div className="flex flex-col gap-1">
        {!collapsed ? (
          <div
            className="px-3 pb-1 pt-2 text-[11px] font-semibold tracking-[0.12em]"
            style={{ color: 'var(--text-dim)' }}
          >
            {title}
          </div>
        ) : (
          showCollapsedDivider && (
            <div
              className="mx-auto my-1 h-px w-6 rounded-full"
              style={{ backgroundColor: 'var(--border-strong)' }}
            />
          )
        )}
        {items.map((item) => {
          const Icon = item.icon
          const active = activePage === item.id
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelectPage(item.id)}
              title={collapsed ? item.label : undefined}
              className={`group relative flex items-center rounded-[var(--radius-sm)] text-left text-[13.5px] transition-colors cursor-pointer ${
                collapsed ? 'mx-auto h-10 w-10 justify-center px-0' : 'gap-2.5 px-3 py-2'
              }`}
              style={{
                backgroundColor: active ? 'var(--primary-soft)' : 'transparent',
                color: active ? 'var(--primary)' : 'var(--text)',
                fontWeight: active ? 600 : 500,
              }}
            >
              {active && !collapsed && (
                <span
                  className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full"
                  style={{ backgroundColor: 'var(--primary)' }}
                />
              )}
              <Icon
                size={17}
                strokeWidth={active ? 2.2 : 1.8}
                className="shrink-0 transition-colors"
              />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </button>
          )
        })}
      </div>
    )
  }

  return (
    <div className="relative flex h-full w-full overflow-hidden">
      {/* 底层壁纸 + 主题柔光遮罩（常驻 DOM 以实现 260ms 丝滑淡入淡出） */}
      {wallpaperUrl && (
        <div
          className="pointer-events-none fixed inset-0 z-0 overflow-hidden transition-opacity duration-300 ease-out"
          style={{ opacity: showWallpaper ? 1 : 0 }}
          aria-hidden="true"
        >
          <img
            src={wallpaperUrl}
            alt=""
            className="h-full w-full object-cover object-center"
          />
          <div
            className="absolute inset-0 transition-all duration-300 ease-out"
            style={{
              backgroundColor: 'var(--overlay-color)',
              opacity: 'var(--overlay-alpha)',
            }}
          />
        </div>
      )}

      {/* 左侧导航轨 */}
      <aside
        className="kk-sidebar relative z-20 flex h-full shrink-0 flex-col transition-[width] duration-200"
        style={{ width: collapsed ? 68 : 214 }}
      >
        {/* 品牌头：折叠态居中展示完整 Logo，展开态展示 Logo + 标题 */}
        <div
          className={`flex h-[54px] items-center ${collapsed ? 'justify-center px-0' : 'px-3.5'}`}
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <button
            type="button"
            onClick={() => collapsed && setCollapsed(false)}
            title={collapsed ? '点击展开导航栏' : 'KKTools'}
            className={`flex items-center gap-2.5 overflow-hidden text-left ${collapsed ? 'cursor-pointer' : 'cursor-default'}`}
          >
            <img
              src="./logo.png"
              alt="KKTools"
              draggable={false}
              className="h-8 w-8 shrink-0 select-none"
            />
            {!collapsed && (
              <div className="min-w-0 leading-tight">
                <div className="flex items-center gap-1.5">
                  <span
                    className="font-mono-num text-[15px] font-bold tracking-[0.06em]"
                    style={{ color: 'var(--text-strong)' }}
                  >
                    KKTools
                  </span>
                  <span
                    className="font-mono-num rounded-full px-1.5 py-[1px] text-[10px] font-semibold"
                    style={{
                      backgroundColor: 'var(--primary-soft)',
                      color: 'var(--primary)',
                    }}
                  >
                    {appVersion}
                  </span>
                </div>
                <div className="text-[10.5px]" style={{ color: 'var(--text-dim)' }}>
                  恋活角色卡画室
                </div>
              </div>
            )}
          </button>
        </div>

        {/* 导航菜单 */}
        <nav className={`flex flex-1 flex-col gap-2.5 overflow-y-auto py-3 ${collapsed ? 'px-2' : 'px-2.5'}`}>
          {renderGroup('studio', '创作与画廊', false)}
          {renderGroup('manage', '整理与仓库', true)}
          <div className="mt-auto pt-2" style={{ borderTop: '1px solid var(--border)' }}>
            {renderGroup('system', '系统', false)}
          </div>
        </nav>
      </aside>

      {/* 右侧主区域 */}
      <div className="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden kk-canvas-pattern">
        {/* 一体式极简顶栏 */}
        <header className="kk-topbar relative z-30 flex h-[54px] shrink-0 items-center justify-between px-4">
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => setCollapsed((v) => !v)}
              className="kk-btn-ghost flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-sm)] cursor-pointer"
              title={collapsed ? '展开左侧导航' : '收起左侧导航'}
              aria-label={collapsed ? '展开左侧导航' : '收起左侧导航'}
            >
              {collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
            </button>
            <div className="flex items-baseline gap-2.5">
              <h1
                className="text-[16px] font-bold tracking-tight"
                style={{ color: 'var(--text-strong)' }}
              >
                {currentNav.label}
              </h1>
              <span
                className="font-mono-num text-[11px] font-medium tracking-[0.14em]"
                style={{ color: 'var(--text-dim)' }}
              >
                {currentNav.en}
              </span>
            </div>
          </div>

          {/* 右侧高频快捷控制 */}
          <div className="flex items-center gap-2">
            {/* 壁纸融合开关 */}
            <button
              type="button"
              onClick={onToggleWallpaper}
              className="kk-btn h-8 px-2.5 text-[12px]"
              style={
                showWallpaper
                  ? {
                      backgroundColor: 'var(--primary-soft)',
                      borderColor: 'var(--primary-border)',
                      color: 'var(--primary)',
                    }
                  : undefined
              }
              title={wallpaperUrl ? '切换壁纸毛玻璃融合' : '先在外观设置中选择壁纸'}
            >
              <ImageIcon size={14} />
              <span>{showWallpaper ? '壁纸融合 · 开' : '壁纸融合'}</span>
            </button>

            {/* 精简 / 完整模式 */}
            <button
              type="button"
              onClick={onToggleUiMode}
              className="kk-btn h-8 px-2.5 text-[12px]"
              title="切换精简/完整功能显示"
            >
              <SlidersHorizontal size={14} />
              <span>{uiMode === 'advanced' ? '完整模式' : '精简模式'}</span>
            </button>

            {/* 主题速切弹出菜单 */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setThemeMenuOpen((v) => !v)}
                className="kk-btn h-8 px-2.5 text-[12px]"
                aria-expanded={themeMenuOpen}
              >
                <Palette size={14} style={{ color: 'var(--primary)' }} />
                <span>{currentThemeMeta.name}</span>
              </button>

              {themeMenuOpen && (
                <>
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setThemeMenuOpen(false)}
                  />
                  <div className="kk-popover absolute right-0 top-10 z-50 w-60 p-2">
                    <div
                      className="px-2 pb-1.5 pt-1 text-[11px] font-semibold tracking-[0.08em]"
                      style={{ color: 'var(--text-dim)' }}
                    >
                      选择界面气质
                    </div>
                    <div className="flex flex-col gap-1">
                      {THEMES.map((t) => {
                        const selected = t.id === theme
                        return (
                          <button
                            key={t.id}
                            type="button"
                            onClick={() => {
                              onChangeTheme(t.id)
                              setThemeMenuOpen(false)
                            }}
                            className="flex items-center justify-between rounded-[var(--radius-sm)] px-2.5 py-2 text-left transition-colors cursor-pointer"
                            style={{
                              backgroundColor: selected ? 'var(--primary-soft)' : 'transparent',
                            }}
                          >
                            <div className="flex items-center gap-2.5">
                              <span
                                className="flex h-5 w-5 overflow-hidden rounded-full border"
                                style={{ borderColor: 'var(--border-strong)' }}
                              >
                                <span
                                  className="h-full w-1/2"
                                  style={{ backgroundColor: t.swatches[0] }}
                                />
                                <span
                                  className="h-full w-1/2"
                                  style={{ backgroundColor: t.swatches[2] }}
                                />
                              </span>
                              <div>
                                <div
                                  className="text-[12.5px] font-semibold leading-tight"
                                  style={{ color: 'var(--text-strong)' }}
                                >
                                  {t.name}
                                </div>
                                <div
                                  className="font-mono-num text-[10px]"
                                  style={{ color: 'var(--text-dim)' }}
                                >
                                  {t.jpName}
                                </div>
                              </div>
                            </div>
                            {selected && <Check size={14} style={{ color: 'var(--primary)' }} />}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </header>

        {/* 主内容视口：key 绑定 activePage 实现切换时的顺滑淡入微浮 */}
        <main className="relative flex-1 overflow-hidden">
          <div key={activePage} className="kk-page-enter h-full w-full">
            {children}
          </div>
        </main>

        {/* 底部极细状态栏 */}
        <footer
          className="kk-topbar flex h-7 shrink-0 items-center justify-between px-4 text-[11.5px]"
          style={{
            borderTop: '1px solid var(--border)',
            borderBottom: 'none',
            color: 'var(--text-muted)',
          }}
        >
          <span className="truncate">{statusText}</span>
          <span className="font-mono-num shrink-0" style={{ color: 'var(--text-dim)' }}>
            {currentThemeMeta.name} · {showWallpaper ? 'GLASS' : 'SOLID'}
          </span>
        </footer>
      </div>

      {/* 轻量非阻断 Toast */}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="kk-popover fixed bottom-10 right-5 z-50 flex items-center gap-2 px-4 py-2.5 text-[13px] font-medium"
          style={{
            borderColor:
              toast.tone === 'error'
                ? 'var(--danger)'
                : toast.tone === 'ok'
                  ? 'var(--success)'
                  : toast.tone === 'warn'
                    ? 'var(--warning)'
                    : 'var(--primary-border)',
            color: 'var(--text-strong)',
          }}
        >
          <span
            className="h-2 w-2 rounded-full"
            style={{
              backgroundColor:
                toast.tone === 'error'
                  ? 'var(--danger)'
                  : toast.tone === 'ok'
                    ? 'var(--success)'
                    : toast.tone === 'warn'
                      ? 'var(--warning)'
                      : 'var(--primary)',
            }}
          />
          <span>{toast.text}</span>
        </div>
      )}
    </div>
  )
}
