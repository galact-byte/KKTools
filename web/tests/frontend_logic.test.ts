import { afterEach, describe, expect, test } from 'bun:test'
import {
  allocateAuthorRenderBudget,
  formatCardTypeBadge,
  getCardConvertCapability,
  isEmptyGuid,
  normalizeDisplayAuthor,
  normalizeUserId,
} from '../src/lib/cardDisplay'
import { backend, cancelAndReleaseTask, waitTask } from '../src/lib/bridge'
import type { CardSummary } from '../src/types/kk'

function makeCard(id: string, author = ''): CardSummary {
  return {
    id,
    path: `E:/Cards/${id}.png`,
    fileName: `${id}.png`,
    type: 'character',
    game: 'KKS',
    name: id,
    author,
    thumbnailUrl: `/thumb/${id}`,
  }
}

describe('cardDisplay helpers', () => {
  test('filters empty or all-zero GUID and KKSID:00000000', () => {
    expect(isEmptyGuid('')).toBe(true)
    expect(isEmptyGuid('00000000-0000-0000-0000-000000000000')).toBe(true)
    expect(isEmptyGuid('00000000')).toBe(true)
    expect(isEmptyGuid('a1b2c3d4-1234-5678-90ab-cdef12345678')).toBe(false)

    expect(normalizeUserId('00000000-0000-0000-0000-000000000000')).toBe('')
    expect(normalizeUserId('12345678-abcd-ef01-2345-6789abcdef01')).toBe(
      '12345678-abcd-ef01-2345-6789abcdef01',
    )

    expect(normalizeDisplayAuthor('KKSID:00000000')).toBe('')
    expect(normalizeDisplayAuthor('kksid:00000000')).toBe('')
    expect(normalizeDisplayAuthor('00000000-0000-0000-0000-000000000000')).toBe('')
    expect(normalizeDisplayAuthor('KKSID:1a2b3c4d')).toBe('KKSID:1a2b3c4d')
    expect(normalizeDisplayAuthor('千年制作部')).toBe('千年制作部')
  })

  test('coordinate with unknown game displays 服装卡 · 版本未知 and only character KK/KKS can convert', () => {
    expect(formatCardTypeBadge('coordinate', '?')).toBe('服装卡 · 版本未知')
    expect(formatCardTypeBadge('coordinate', '')).toBe('服装卡 · 版本未知')
    expect(formatCardTypeBadge('character', 'KK')).toBe('角色卡')

    const charKK = getCardConvertCapability('character', 'KK')
    expect(charKK.canConvert).toBe(true)
    expect(charKK.targetGame).toBe('KKS')

    const charKKS = getCardConvertCapability('character', 'KKS')
    expect(charKKS.canConvert).toBe(true)
    expect(charKKS.targetGame).toBe('KK')

    const coordUnknown = getCardConvertCapability('coordinate', '?')
    expect(coordUnknown.canConvert).toBe(false)
    expect(coordUnknown.reason).toContain('服装卡')

    const coordKKS = getCardConvertCapability('coordinate', 'KKS')
    expect(coordKKS.canConvert).toBe(false)

    const sceneCard = getCardConvertCapability('scene', 'KKS')
    expect(sceneCard.canConvert).toBe(false)
    expect(sceneCard.reason).toContain('场景卡')

    const charUnknown = getCardConvertCapability('character', '?')
    expect(charUnknown.canConvert).toBe(false)
  })

  test('author render budget caps total rendered card DOM across all groups', () => {
    const groups = Array.from({ length: 10 }, (_, gi) => ({
      key: `author-${gi}`,
      items: Array.from({ length: 50 }, (__, ci) => makeCard(`g${gi}-c${ci}`, `author-${gi}`)),
    }))

    const plan = allocateAuthorRenderBudget(groups, {
      totalBudget: 120,
      defaultGroupLimit: 40,
      collapsedGroups: { 'author-1': true },
      groupLimits: {},
    })

    expect(plan.totalRendered).toBe(120)
    expect(plan.allocations['author-0'].renderCount).toBe(40)
    expect(plan.allocations['author-1'].renderCount).toBe(0)
    expect(plan.allocations['author-2'].renderCount).toBe(40)
    expect(plan.allocations['author-3'].renderCount).toBe(40)
    expect(plan.allocations['author-4'].renderCount).toBe(0)
    expect(plan.allocations['author-4'].deferredByBudget).toBe(true)
    expect(plan.hasDeferredCards).toBe(true)
  })
})

describe('bridge paged scan, query and task release', () => {
  const originalWindow = (globalThis as Record<string, unknown>).window

  afterEach(() => {
    if (originalWindow === undefined) {
      delete (globalThis as Record<string, unknown>).window
    } else {
      ;(globalThis as Record<string, unknown>).window = originalWindow
    }
  })

  function mockPywebview(api: Record<string, (...args: unknown[]) => Promise<unknown>>) {
    ;(globalThis as Record<string, unknown>).window = {
      pywebview: { api },
      setTimeout: globalThis.setTimeout,
      clearTimeout: globalThis.clearTimeout,
    }
  }

  test('startScanDirectory passes boolean paged=true and queryCardPage passes options', async () => {
    const calls: Array<{ method: string; args: unknown[] }> = []
    mockPywebview({
      start_scan_directory: async (...args) => {
        calls.push({ method: 'start_scan_directory', args })
        return { ok: true, data: { taskId: 'scan-1' } }
      },
      query_card_page: async (...args) => {
        calls.push({ method: 'query_card_page', args })
        return {
          ok: true,
          data: {
            directory: 'E:/Cards',
            recursive: true,
            total: 1000,
            offset: 0,
            limit: 120,
            hasMore: true,
            indexed: true,
            complete: true,
            items: [],
          },
        }
      },
    })

    const scanRes = await backend.startScanDirectory('E:/Cards', true, true)
    expect(scanRes.ok).toBe(true)
    expect(calls[0]).toEqual({
      method: 'start_scan_directory',
      args: ['E:/Cards', true, true],
    })
    expect(typeof calls[0].args[2]).toBe('boolean')

    const pageRes = await backend.queryCardPage('E:/Cards', {
      recursive: true,
      offset: 0,
      limit: 120,
      author: '',
      search: 'test',
    })
    expect(pageRes.ok).toBe(true)
    expect(pageRes.data?.indexed).toBe(true)
    expect(calls[1].method).toBe('query_card_page')
  })

  test('waitTask releases finished task and preserves resultExpired flag', async () => {
    const calls: Array<{ method: string; args: unknown[] }> = []
    mockPywebview({
      poll_task: async (taskId) => {
        calls.push({ method: 'poll_task', args: [taskId] })
        return {
          ok: true,
          data: {
            id: taskId,
            status: 'done',
            current: 10,
            total: 10,
            percent: 100,
            message: 'done',
            result: null,
            resultExpired: true,
          },
        }
      },
      release_task: async (taskId) => {
        calls.push({ method: 'release_task', args: [taskId] })
        return { ok: true, data: true }
      },
    })

    const res = await waitTask<{ total: number }>('task-exp', undefined, 5)
    expect(res.ok).toBe(true)
    expect(res.resultExpired).toBe(true)
    expect(calls.map((c) => c.method)).toEqual(['poll_task', 'release_task'])
  })

  test('cancelAndReleaseTask cancels running task, waits until cancelled, then releases', async () => {
    const seq: string[] = []
    let polls = 0
    mockPywebview({
      cancel_task: async () => {
        seq.push('cancel')
        return { ok: true, data: true }
      },
      poll_task: async (taskId) => {
        polls += 1
        seq.push(`poll-${polls}`)
        if (polls === 1) {
          return {
            ok: true,
            data: {
              id: taskId,
              status: 'running',
              current: 1,
              total: 10,
              percent: 10,
              message: '正在取消…',
            },
          }
        }
        return {
          ok: true,
          data: {
            id: taskId,
            status: 'cancelled',
            current: 1,
            total: 10,
            percent: 10,
            message: '已取消扫描',
          },
        }
      },
      release_task: async () => {
        seq.push('release')
        return { ok: true, data: true }
      },
    })

    await cancelAndReleaseTask('task-run', 5)
    expect(seq).toEqual(['cancel', 'poll-1', 'poll-2', 'release'])
  })
})
