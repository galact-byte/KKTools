import { TYPE_META } from '../data/constants'
import type { CardSummary, CardType } from '../types/kk'

export function isEmptyGuid(raw?: string | null): boolean {
  const s = (raw || '').trim()
  if (!s) return true
  return s.replace(/-/g, '').replace(/0/g, '') === ''
}

export function normalizeUserId(raw?: string | null): string {
  const s = (raw || '').trim()
  if (!s || isEmptyGuid(s)) return ''
  return s
}

export function normalizeDisplayAuthor(raw?: string | null): string {
  const s = (raw || '').trim()
  if (!s) return ''
  if (isEmptyGuid(s)) return ''
  const upper = s.toUpperCase()
  if (upper.startsWith('KKSID:')) {
    const rest = upper.slice('KKSID:'.length).trim()
    if (!rest || isEmptyGuid(rest)) return ''
  }
  return s
}

export function formatCardTypeBadge(type: CardType, game?: string): string {
  if (type === 'coordinate' && (!game || game === '?')) {
    return '服装卡 · 版本未知'
  }
  return TYPE_META[type]?.label ?? '其他'
}

export interface CardConvertCapability {
  canConvert: boolean
  targetGame: 'KK' | 'KKS' | null
  reason: string
}

export function getCardConvertCapability(
  type: CardType,
  game?: string,
): CardConvertCapability {
  if (type === 'coordinate') {
    return {
      canConvert: false,
      targetGame: null,
      reason: '独立服装卡暂不支持 1代 / 2代 互转',
    }
  }
  if (type === 'scene') {
    return {
      canConvert: false,
      targetGame: null,
      reason: '场景卡暂不支持 1代 / 2代 互转',
    }
  }
  if (type !== 'character') {
    return {
      canConvert: false,
      targetGame: null,
      reason: '仅支持 KK / KKS 角色卡互转',
    }
  }
  if (game === 'KK') {
    return { canConvert: true, targetGame: 'KKS', reason: '' }
  }
  if (game === 'KKS') {
    return { canConvert: true, targetGame: 'KK', reason: '' }
  }
  return {
    canConvert: false,
    targetGame: null,
    reason: '仅支持 KK / KKS 角色卡互转（当前版本未知或不受支持）',
  }
}

export interface AuthorGroupBudgetInput {
  key: string
  items: CardSummary[]
  totalCount?: number
}

export interface AuthorGroupAllocation {
  renderCount: number
  deferredByBudget: boolean
}

export interface AuthorRenderBudgetPlan {
  totalRendered: number
  remainingBudget: number
  hasDeferredCards: boolean
  allocations: Record<string, AuthorGroupAllocation>
}

export function allocateAuthorRenderBudget(
  groups: AuthorGroupBudgetInput[],
  opts: {
    totalBudget: number
    defaultGroupLimit: number
    collapsedGroups: Record<string, boolean>
    groupLimits: Record<string, number>
  },
): AuthorRenderBudgetPlan {
  const safeBudget = Math.max(0, Math.floor(opts.totalBudget))
  let used = 0
  let hasDeferredCards = false
  const allocations: Record<string, AuthorGroupAllocation> = {}

  for (const group of groups) {
    const collapsed = Boolean(opts.collapsedGroups[group.key])
    if (collapsed) {
      allocations[group.key] = { renderCount: 0, deferredByBudget: false }
      continue
    }

    const desiredCap = Math.max(1, opts.groupLimits[group.key] ?? opts.defaultGroupLimit)
    const desiredCount = Math.min(group.items.length, desiredCap)
    const remaining = Math.max(0, safeBudget - used)
    const renderCount = Math.min(desiredCount, remaining)
    const deferredByBudget = desiredCount > renderCount

    used += renderCount
    if (deferredByBudget) {
      hasDeferredCards = true
    }
    allocations[group.key] = { renderCount, deferredByBudget }
  }

  return {
    totalRendered: used,
    remainingBudget: Math.max(0, safeBudget - used),
    hasDeferredCards,
    allocations,
  }
}
