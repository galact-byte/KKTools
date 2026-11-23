import React, { useMemo, useState } from 'react'
import {
  Check,
  Code2,
  Copy,
  FilePlus2,
  FolderOpen,
  Heart,
  ImagePlus,
  Layers,
  RotateCcw,
  Save,
  ShieldAlert,
  Sparkles,
  UserRound,
} from 'lucide-react'
import {
  ANSWER_LABELS,
  ATTRIBUTE_LABELS,
  BLOOD_TYPES,
  DENIAL_LABELS,
  KK_PERSONALITIES,
} from '../data/constants'
import type { CardDetail, CardModCheckResult } from '../types/kk'

interface EditorPageProps {
  card: CardDetail | null
  coverPreviewUrl: string
  dirty: boolean
  saving: boolean
  modCheck: CardModCheckResult | null
  checkingMods: boolean
  inModal?: boolean
  onPickCardFile: () => void
  onPickCover: () => void
  onUpdateParam: (updater: (param: CardDetail['parameter']) => CardDetail['parameter']) => void
  onSaveAs: () => void
  onSaveOverwrite: () => void
  onReset: () => void
  onCopyModIds: () => void
  onCheckCardMods: () => void
}

type EditorTab = 'profile' | 'traits' | 'mods' | 'raw'

export const EditorPage: React.FC<EditorPageProps> = ({
  card,
  coverPreviewUrl,
  dirty,
  saving,
  modCheck,
  checkingMods,
  inModal = false,
  onPickCardFile,
  onPickCover,
  onUpdateParam,
  onSaveAs,
  onSaveOverwrite,
  onReset,
  onCopyModIds,
  onCheckCardMods,
}) => {
  const [tab, setTab] = useState<EditorTab>('profile')

  const fullName = useMemo(() => {
    if (!card) return ''
    const { lastname, firstname } = card.parameter
    return [lastname, firstname].filter(Boolean).join(' ') || card.fileName
  }, [card])

  const countChecked = (rec: Record<string, boolean>) => {
    const entries = Object.entries(rec)
    return [entries.filter(([, v]) => v).length, entries.length] as const
  }

  if (!card) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="kk-surface flex max-w-md flex-col items-center gap-3 p-10 text-center">
          <div
            className="flex h-12 w-12 items-center justify-center rounded-full"
            style={{ backgroundColor: 'var(--primary-soft)', color: 'var(--primary)' }}
          >
            <UserRound size={22} />
          </div>
          <div className="text-[16px] font-bold" style={{ color: 'var(--text-strong)' }}>
            选择一张角色卡开始编辑
          </div>
          <p className="text-[13px]" style={{ color: 'var(--text-muted)' }}>
            你可以从「卡片画廊」双击任意角色卡进入，或直接打开本地 PNG 角色卡文件。只重写修改过的 Parameter 块，其余二进制块原样保留。
          </p>
          <button type="button" onClick={onPickCardFile} className="kk-btn kk-btn-primary mt-1">
            <FolderOpen size={14} />
            <span>打开本地角色卡</span>
          </button>
        </div>
      </div>
    )
  }

  const p = card.parameter
  const [ansOn, ansTotal] = countChecked(p.awnser)
  const [attrOn, attrTotal] = countChecked(p.attribute)
  const [denOn, denTotal] = countChecked(p.denial)
  const displayCover = coverPreviewUrl || card.thumbnailUrl

  const toggleMapKey = (bucket: 'awnser' | 'attribute' | 'denial', key: string) => {
    onUpdateParam((cur) => ({
      ...cur,
      [bucket]: {
        ...cur[bucket],
        [key]: !cur[bucket][key],
      },
    }))
  }

  const renderPillMatrix = (
    title: string,
    bucket: 'awnser' | 'attribute' | 'denial',
    labels: Record<string, string>,
    tone: 'primary' | 'sakura',
    checked: number,
    total: number,
  ) => {
    const keys = Object.keys(p[bucket])
    return (
      <section className="kk-surface flex flex-col gap-3 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className="h-3.5 w-[3px] rounded-full"
              style={{ backgroundColor: tone === 'sakura' ? 'var(--sakura)' : 'var(--primary)' }}
            />
            <h3 className="text-[14px] font-semibold" style={{ color: 'var(--text-strong)' }}>
              {title}
            </h3>
            <span
              className="font-mono-num rounded-full px-2 py-0.5 text-[11px] font-semibold"
              style={{
                backgroundColor: tone === 'sakura' ? 'var(--sakura-soft)' : 'var(--primary-soft)',
                color: tone === 'sakura' ? 'var(--sakura)' : 'var(--primary)',
              }}
            >
              {checked} / {total}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              className="kk-btn-ghost rounded-[6px] px-2 py-1 text-[11.5px] cursor-pointer"
              onClick={() =>
                onUpdateParam((cur) => ({
                  ...cur,
                  [bucket]: Object.fromEntries(keys.map((k) => [k, true])),
                }))
              }
            >
              全选
            </button>
            <button
              type="button"
              className="kk-btn-ghost rounded-[6px] px-2 py-1 text-[11.5px] cursor-pointer"
              onClick={() =>
                onUpdateParam((cur) => ({
                  ...cur,
                  [bucket]: Object.fromEntries(keys.map((k) => [k, false])),
                }))
              }
            >
              清空
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {keys.map((k) => {
            const active = Boolean(p[bucket][k])
            const label = labels[k] ?? k
            const accentBg = tone === 'sakura' ? 'var(--sakura-soft)' : 'var(--primary-soft)'
            const accentBorder = tone === 'sakura' ? 'var(--sakura-border)' : 'var(--primary-border)'
            const accentColor = tone === 'sakura' ? 'var(--sakura)' : 'var(--primary)'
            return (
              <button
                key={k}
                type="button"
                onClick={() => toggleMapKey(bucket, k)}
                aria-pressed={active}
                className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12.5px] font-medium transition-colors cursor-pointer"
                style={{
                  backgroundColor: active ? accentBg : 'var(--surface-alt)',
                  border: `1px solid ${active ? accentBorder : 'var(--border)'}`,
                  color: active ? accentColor : 'var(--text-muted)',
                }}
              >
                {active && <Check size={12} strokeWidth={2.6} />}
                <span>{label}</span>
              </button>
            )
          })}
        </div>
      </section>
    )
  }

  return (
    <fieldset disabled={saving} className={`m-0 min-w-0 border-0 flex h-full gap-4 overflow-hidden ${inModal ? 'p-4' : 'px-5 py-4'}`}>
      {/* 左侧：角色立绘卡座（视觉重心） */}
      <aside
        className={`kk-surface flex shrink-0 flex-col overflow-hidden ${
          inModal ? 'w-[288px]' : 'w-[312px]'
        }`}
      >
        <div className="flex flex-1 flex-col gap-3.5 overflow-y-auto p-4">
          <div
            className="group relative shrink-0 overflow-hidden rounded-[var(--radius-md)] border"
            style={{
              aspectRatio: '5 / 7',
              borderColor: 'var(--border)',
              backgroundColor: 'var(--surface-alt)',
            }}
          >
            <img src={displayCover} alt={fullName} className="h-full w-full object-cover" />
            <div className="absolute left-2.5 top-2.5 flex items-center gap-1.5">
              <span
                className="font-mono-num rounded-[6px] px-2 py-0.5 text-[11px] font-bold backdrop-blur-md"
                style={{ backgroundColor: 'rgba(15, 25, 45, 0.72)', color: '#ffffff' }}
              >
                {card.game}
              </span>
              {card.isDemo && (
                <span
                  className="rounded-[6px] px-2 py-0.5 text-[10.5px] font-semibold backdrop-blur-md"
                  style={{ backgroundColor: 'rgba(224, 82, 124, 0.85)', color: '#ffffff' }}
                >
                  示范档案
                </span>
              )}
            </div>
            {dirty && (
              <span
                className="absolute right-2.5 top-2.5 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold backdrop-blur-md"
                style={{ backgroundColor: 'rgba(184, 116, 20, 0.9)', color: '#ffffff' }}
              >
                未保存改动
              </span>
            )}
            <button
              type="button"
              onClick={onPickCover}
              className="absolute bottom-2.5 right-2.5 inline-flex items-center gap-1.5 rounded-[8px] px-2.5 py-1.5 text-[11.5px] font-semibold opacity-0 backdrop-blur-md transition-opacity duration-150 group-hover:opacity-100 cursor-pointer"
              style={{ backgroundColor: 'rgba(15, 25, 45, 0.78)', color: '#ffffff' }}
            >
              <ImagePlus size={13} />
              <span>替换封面</span>
            </button>
          </div>

          {/* 角色档案头 */}
          <div>
            <h2
              className="font-display text-[20px] font-bold leading-snug"
              style={{ color: 'var(--text-strong)' }}
            >
              {fullName}
            </h2>
            <div className="mt-0.5 text-[12px]" style={{ color: 'var(--text-muted)' }}>
              {card.gameName} · v{card.version}
            </div>
            <div
              className="font-mono-num mt-1 truncate text-[11px]"
              style={{ color: 'var(--text-dim)' }}
              title={card.path}
            >
              {card.fileName}
            </div>
          </div>

          {/* 快速档案概览 */}
          <div className="kk-surface-alt grid grid-cols-3 gap-2 p-2.5 text-center">
            <div>
              <div className="text-[10.5px]" style={{ color: 'var(--text-dim)' }}>
                生日
              </div>
              <div
                className="font-mono-num mt-0.5 text-[12.5px] font-semibold"
                style={{ color: 'var(--text-strong)' }}
              >
                {String(p.birthMonth).padStart(2, '0')}/{String(p.birthDay).padStart(2, '0')}
              </div>
            </div>
            <div
              style={{
                borderLeft: '1px solid var(--border)',
                borderRight: '1px solid var(--border)',
              }}
            >
              <div className="text-[10.5px]" style={{ color: 'var(--text-dim)' }}>
                血型
              </div>
              <div
                className="font-mono-num mt-0.5 text-[12.5px] font-semibold"
                style={{ color: 'var(--text-strong)' }}
              >
                {typeof p.bloodType === 'number' ? BLOOD_TYPES[p.bloodType] ?? '?' : p.bloodType}型
              </div>
            </div>
            <div>
              <div className="text-[10.5px]" style={{ color: 'var(--text-dim)' }}>
                Mod 依赖
              </div>
              <div
                className="font-mono-num mt-0.5 text-[12.5px] font-semibold"
                style={{ color: 'var(--primary)' }}
              >
                {card.modIds.length}
              </div>
            </div>
          </div>
        </div>

        {/* 底部保存操作栏 */}
        <div
          className="flex flex-col gap-2 p-3.5"
          style={{ borderTop: '1px solid var(--border)' }}
        >
          <button
            type="button"
            disabled={saving}
            onClick={onSaveAs}
            className="kk-btn kk-btn-primary w-full py-2"
          >
            <FilePlus2 size={14} />
            <span>{saving ? '保存中…' : '另存为新卡'}</span>
          </button>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              disabled={saving || !dirty}
              onClick={onSaveOverwrite}
              className="kk-btn text-[12px]"
            >
              <Save size={13} />
              <span>覆盖原卡</span>
            </button>
            <button
              type="button"
              disabled={!dirty}
              onClick={onReset}
              className="kk-btn text-[12px]"
            >
              <RotateCcw size={13} />
              <span>还原改动</span>
            </button>
          </div>
          {!inModal && (
            <button
              type="button"
              onClick={onPickCardFile}
              className="kk-btn-ghost mt-0.5 flex items-center justify-center gap-1.5 rounded-[var(--radius-sm)] py-1.5 text-[12px] cursor-pointer"
            >
              <FolderOpen size={13} />
              <span>打开本地角色卡…</span>
            </button>
          )}
        </div>
      </aside>

      {/* 右侧：结构化档案工作区 */}
      <div className="flex min-w-0 flex-1 flex-col gap-3.5 overflow-hidden">
        {/* 精致标签栏 */}
        <div className="kk-surface flex shrink-0 items-center justify-between px-3 py-2">
          <div className="flex items-center gap-1">
            {(
              [
                { id: 'profile', label: '基础档案', icon: UserRound },
                { id: 'traits', label: `性格与偏好 (${ansOn + attrOn + denOn})`, icon: Heart },
                { id: 'mods', label: `Mod 依赖 (${card.modIds.length})`, icon: Layers },
                { id: 'raw', label: '原始块参数', icon: Code2 },
              ] as const
            ).map(({ id, label, icon: Icon }) => {
              const active = tab === id
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setTab(id)}
                  className="inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] px-3 py-1.5 text-[13px] font-medium transition-colors cursor-pointer"
                  style={{
                    backgroundColor: active ? 'var(--primary-soft)' : 'transparent',
                    color: active ? 'var(--primary)' : 'var(--text-muted)',
                    fontWeight: active ? 600 : 500,
                  }}
                >
                  <Icon size={14} />
                  <span>{label}</span>
                </button>
              )
            })}
          </div>

          <span className="font-mono-num text-[11.5px]" style={{ color: 'var(--text-dim)' }}>
            {card.blockNames.length} DATA BLOCKS
          </span>
        </div>

        {/* 标签内容滚动区（带轻柔和切换动画） */}
        <div className="flex-1 overflow-y-auto pr-1">
          <div key={tab} className="kk-tab-enter">
            {tab === 'profile' && (
              <div className="flex flex-col gap-3.5 pb-4">
                <section className="kk-surface flex flex-col gap-4 p-5">
                  <div className="flex items-center gap-2">
                    <span
                      className="h-3.5 w-[3px] rounded-full"
                      style={{ backgroundColor: 'var(--primary)' }}
                    />
                    <h3 className="text-[14px] font-semibold" style={{ color: 'var(--text-strong)' }}>
                      姓名与称呼
                    </h3>
                  </div>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <label className="flex flex-col gap-1.5">
                      <span className="text-[12px] font-medium" style={{ color: 'var(--text-muted)' }}>
                        姓 (Lastname)
                      </span>
                      <input
                        type="text"
                        value={p.lastname}
                        onChange={(e) => onUpdateParam((c) => ({ ...c, lastname: e.target.value }))}
                        className="kk-input"
                      />
                    </label>
                    <label className="flex flex-col gap-1.5">
                      <span className="text-[12px] font-medium" style={{ color: 'var(--text-muted)' }}>
                        名 (Firstname)
                      </span>
                      <input
                        type="text"
                        value={p.firstname}
                        onChange={(e) => onUpdateParam((c) => ({ ...c, firstname: e.target.value }))}
                        className="kk-input"
                      />
                    </label>
                    <label className="flex flex-col gap-1.5">
                      <span className="text-[12px] font-medium" style={{ color: 'var(--text-muted)' }}>
                        昵称 (Nickname)
                      </span>
                      <input
                        type="text"
                        value={p.nickname}
                        onChange={(e) => onUpdateParam((c) => ({ ...c, nickname: e.target.value }))}
                        className="kk-input"
                      />
                    </label>
                  </div>
                </section>

                <section className="kk-surface flex flex-col gap-4 p-5">
                  <div className="flex items-center gap-2">
                    <span
                      className="h-3.5 w-[3px] rounded-full"
                      style={{ backgroundColor: 'var(--sakura)' }}
                    />
                    <h3 className="text-[14px] font-semibold" style={{ color: 'var(--text-strong)' }}>
                      学院档案设定
                    </h3>
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[12px] font-medium" style={{ color: 'var(--text-muted)' }}>
                        性别
                      </span>
                      <div className="grid grid-cols-2 gap-2">
                        {[
                          { val: 1, label: '女性角色' },
                          { val: 0, label: '男性角色' },
                        ].map((opt) => {
                          const active = p.sex === opt.val
                          return (
                            <button
                              key={opt.val}
                              type="button"
                              onClick={() => onUpdateParam((c) => ({ ...c, sex: opt.val }))}
                              className="rounded-[var(--radius-sm)] py-2 text-[13px] font-medium transition-colors cursor-pointer"
                              style={{
                                backgroundColor: active ? 'var(--primary-soft)' : 'var(--surface-alt)',
                                border: `1px solid ${active ? 'var(--primary-border)' : 'var(--border)'}`,
                                color: active ? 'var(--primary)' : 'var(--text-muted)',
                              }}
                            >
                              {opt.label}
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    <div className="flex flex-col gap-1.5">
                      <span className="text-[12px] font-medium" style={{ color: 'var(--text-muted)' }}>
                        血型
                      </span>
                      <div className="grid grid-cols-4 gap-2">
                        {BLOOD_TYPES.map((bt, idx) => {
                          const active = p.bloodType === idx || p.bloodType === bt
                          return (
                            <button
                              key={bt}
                              type="button"
                              onClick={() => onUpdateParam((c) => ({ ...c, bloodType: idx }))}
                              className="font-mono-num rounded-[var(--radius-sm)] py-2 text-[13px] font-semibold transition-colors cursor-pointer"
                              style={{
                                backgroundColor: active ? 'var(--sakura-soft)' : 'var(--surface-alt)',
                                border: `1px solid ${active ? 'var(--sakura-border)' : 'var(--border)'}`,
                                color: active ? 'var(--sakura)' : 'var(--text-muted)',
                              }}
                            >
                              {bt}
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    <label className="flex flex-col gap-1.5">
                      <span className="text-[12px] font-medium" style={{ color: 'var(--text-muted)' }}>
                        性格声线
                      </span>
                      <select
                        value={typeof p.personality === 'number' ? p.personality : 0}
                        onChange={(e) =>
                          onUpdateParam((c) => ({ ...c, personality: Number(e.target.value) }))
                        }
                        className="kk-input"
                      >
                        {KK_PERSONALITIES.map((item) => (
                          <option key={item.id} value={item.id}>
                            {String(item.id).padStart(2, '0')} · {item.label}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="flex flex-col gap-1.5">
                      <span className="text-[12px] font-medium" style={{ color: 'var(--text-muted)' }}>
                        所属社团 / 编号
                      </span>
                      <input
                        type="text"
                        value={String(p.clubActivities)}
                        onChange={(e) =>
                          onUpdateParam((c) => ({ ...c, clubActivities: e.target.value }))
                        }
                        className="kk-input"
                      />
                    </label>

                    <div className="flex flex-col gap-1.5 md:col-span-2">
                      <span className="text-[12px] font-medium" style={{ color: 'var(--text-muted)' }}>
                        生日
                      </span>
                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2">
                          <input
                            type="number"
                            min={1}
                            max={12}
                            value={p.birthMonth}
                            onChange={(e) =>
                              onUpdateParam((c) => ({
                                ...c,
                                birthMonth: Math.max(1, Math.min(12, Number(e.target.value) || 1)),
                              }))
                            }
                            className="kk-input font-mono-num w-20 text-center"
                          />
                          <span className="text-[13px]" style={{ color: 'var(--text-muted)' }}>
                            月
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <input
                            type="number"
                            min={1}
                            max={31}
                            value={p.birthDay}
                            onChange={(e) =>
                              onUpdateParam((c) => ({
                                ...c,
                                birthDay: Math.max(1, Math.min(31, Number(e.target.value) || 1)),
                              }))
                            }
                            className="kk-input font-mono-num w-20 text-center"
                          />
                          <span className="text-[13px]" style={{ color: 'var(--text-muted)' }}>
                            日
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>
              </div>
            )}

            {tab === 'traits' && (
              <div className="flex flex-col gap-3.5 pb-4">
                {renderPillMatrix('日常偏好（提问项）', 'awnser', ANSWER_LABELS, 'primary', ansOn, ansTotal)}
                {renderPillMatrix('角色特点（属性标签）', 'attribute', ATTRIBUTE_LABELS, 'sakura', attrOn, attrTotal)}
                {renderPillMatrix('互动接受度（Denial）', 'denial', DENIAL_LABELS, 'primary', denOn, denTotal)}
              </div>
            )}

            {tab === 'mods' && (
              <section className="kk-surface flex flex-col gap-3 p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Sparkles size={15} style={{ color: 'var(--primary)' }} />
                    <h3 className="text-[14px] font-semibold" style={{ color: 'var(--text-strong)' }}>
                      卡片引用的 Zipmod GUID 清单
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    {!card.isDemo && (
                      <button
                        type="button"
                        disabled={checkingMods}
                        onClick={onCheckCardMods}
                        className="kk-btn text-[12px]"
                      >
                        <ShieldAlert size={13} />
                        <span>{checkingMods ? '比对中…' : '对照本地仓库检测缺失'}</span>
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={onCopyModIds}
                      disabled={card.modIds.length === 0}
                      className="kk-btn text-[12px]"
                    >
                      <Copy size={13} />
                      <span>复制全部 GUID</span>
                    </button>
                  </div>
                </div>

                {modCheck && (
                  <div
                    className="kk-surface-alt flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 text-[12.5px]"
                    style={{
                      borderColor: modCheck.missing.length > 0 ? 'var(--danger)' : 'var(--success)',
                    }}
                  >
                    <span style={{ color: 'var(--text-strong)' }}>
                      检测结果：已安装{' '}
                      <strong className="font-mono-num" style={{ color: 'var(--success)' }}>
                        {modCheck.present.length}
                      </strong>{' '}
                      项 · 缺失{' '}
                      <strong
                        className="font-mono-num"
                        style={{
                          color: modCheck.missing.length > 0 ? 'var(--danger)' : 'var(--success)',
                        }}
                      >
                        {modCheck.missing.length}
                      </strong>{' '}
                      项
                    </span>
                  </div>
                )}

                {card.modIds.length === 0 ? (
                  <div className="py-10 text-center text-[13px]" style={{ color: 'var(--text-dim)' }}>
                    未检测到第三方 Mod 依赖（纯原版角色卡）。
                  </div>
                ) : (
                  <div className="flex flex-col gap-1.5">
                    {card.modIds.map((guid, idx) => {
                      const isMissing = modCheck?.missing.includes(guid)
                      const isPresent = modCheck?.present.includes(guid)
                      return (
                        <div
                          key={guid}
                          className="kk-surface-alt flex items-center justify-between px-3 py-2 text-[12.5px]"
                        >
                          <div className="flex items-center gap-2.5 overflow-hidden">
                            <span
                              className="font-mono-num w-6 text-right text-[11px]"
                              style={{ color: 'var(--text-dim)' }}
                            >
                              {String(idx + 1).padStart(2, '0')}
                            </span>
                            <code
                              className="font-mono-num truncate"
                              style={{ color: 'var(--text-strong)' }}
                            >
                              {guid}
                            </code>
                          </div>
                          {isMissing && (
                            <span
                              className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
                              style={{ backgroundColor: 'var(--danger-soft)', color: 'var(--danger)' }}
                            >
                              缺失
                            </span>
                          )}
                          {isPresent && (
                            <span
                              className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
                              style={{ backgroundColor: 'var(--success-soft)', color: 'var(--success)' }}
                            >
                              已就绪
                            </span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </section>
            )}

            {tab === 'raw' && (
              <section className="kk-surface flex flex-col gap-3 p-5">
                <h3 className="text-[14px] font-semibold" style={{ color: 'var(--text-strong)' }}>
                  Parameter 标量字段与二进制块
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {card.blockNames.map((bn) => (
                    <span
                      key={bn}
                      className="font-mono-num rounded-[6px] px-2 py-0.5 text-[11.5px]"
                      style={{
                        backgroundColor: 'var(--primary-soft)',
                        color: 'var(--primary)',
                      }}
                    >
                      {bn}
                    </span>
                  ))}
                </div>
                <div className="kk-surface-alt overflow-hidden">
                  <table className="w-full border-collapse text-[12.5px]">
                    <tbody>
                      {Object.entries(p.rawScalars).map(([k, v]) => (
                        <tr key={k} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td
                            className="font-mono-num w-44 px-3 py-2 font-medium"
                            style={{ color: 'var(--text-muted)' }}
                          >
                            {k}
                          </td>
                          <td className="px-3 py-2" style={{ color: 'var(--text-strong)' }}>
                            {String(v)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </div>
        </div>
      </div>
    </fieldset>
  )
}
