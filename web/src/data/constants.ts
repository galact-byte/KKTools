import type { CardType, ThemeId } from '../types/kk'

export const TYPE_META: Record<
  CardType,
  { label: string; short: string; tone: 'primary' | 'sakura' | 'success' | 'neutral' }
> = {
  character: { label: '角色卡', short: 'CHARA', tone: 'primary' },
  coordinate: { label: '服装卡', short: 'COORD', tone: 'sakura' },
  scene: { label: '场景卡', short: 'SCENE', tone: 'success' },
  other: { label: '其它图片', short: 'OTHER', tone: 'neutral' },
}

export const BLOOD_TYPES = ['A', 'B', 'O', 'AB'] as const

export const KK_PERSONALITIES: Array<{ id: number; label: string }> = [
  { id: 0, label: '冷静' },
  { id: 1, label: '天真' },
  { id: 2, label: '高傲' },
  { id: 3, label: '纯朴' },
  { id: 4, label: '无口' },
  { id: 5, label: '认真' },
  { id: 6, label: '傲娇' },
  { id: 7, label: '妹系' },
  { id: 8, label: '姐系' },
  { id: 9, label: '温柔' },
  { id: 10, label: '活泼' },
  { id: 11, label: '文静' },
  { id: 12, label: '腹黑' },
  { id: 13, label: '病娇' },
  { id: 14, label: '中二' },
  { id: 15, label: '天然' },
  { id: 16, label: '诱惑' },
  { id: 17, label: '怪异' },
]

export const ANSWER_LABELS: Record<string, string> = {
  animal: '喜欢小动物',
  eat: '喜欢美食',
  cook: '擅长料理',
  exercise: '擅长运动',
  study: '擅长学习',
  fashionable: '擅长化妆',
  blackCoffee: '喜欢无糖咖啡',
  spicy: '喜欢吃辣',
  sweet: '喜欢甜食',
}

export const DENIAL_LABELS: Record<string, string> = {
  kiss: '接吻',
  aibu: '爱抚',
  anal: '肛交',
  massage: '按摩',
  notCondom: '无套',
}

export const ATTRIBUTE_LABELS: Record<string, string> = {
  hinnyo: '频尿',
  harapeko: '大胃王',
  donkan: '迟钝',
  choroi: '单纯好骗',
  bitch: '淫荡',
  mutturi: '闷骚',
  dokusyo: '爱读书',
  ongaku: '爱音乐',
  kappatu: '活泼',
  ukemi: '被动',
  friendly: '友善',
  kireizuki: '爱干净',
  taida: '懒散',
  sinsyutu: '积极进取',
  hitori: '喜欢独处',
  undo: '爱运动',
  majime: '认真',
  likeGirls: '喜欢女生',
  okute: '晚熟',
  active: '主动',
  info: '消息灵通',
  love: '恋爱脑',
  talk: '健谈',
  nakama: '重视伙伴',
  nonbiri: '悠闲',
  lonely: '怕寂寞',
}

export interface ThemeMeta {
  id: ThemeId
  name: string
  jpName: string
  desc: string
  variant: 'light' | 'dark'
  swatches: [string, string, string, string] // bg, surface, primary, accent
}

export const THEMES: ThemeMeta[] = [
  {
    id: 'sora_light',
    name: '晴空·画室',
    jpName: 'SORA STUDIO',
    desc: '清透瓷白与晴空蔚蓝，搭配浅樱桃点缀，壁纸融合最自然',
    variant: 'light',
    swatches: ['#eef4fc', '#ffffff', '#1a73e8', '#e0527c'],
  },
  {
    id: 'washi_light',
    name: '和纸·午后',
    jpName: 'WASHI PAPER',
    desc: '日系暖调和纸底色与绀青墨韵，长时间浏览柔和不刺眼',
    variant: 'light',
    swatches: ['#f4efe6', '#fffdf9', '#295f8d', '#c9624a'],
  },
  {
    id: 'tsukiyo_dark',
    name: '月夜·星图',
    jpName: 'TSUKIYO DARK',
    desc: '深海靛夜护眼暗色与霜蓝通透面板，夜间修卡氛围拉满',
    variant: 'dark',
    swatches: ['#0e1420', '#151d2d', '#4ea1ff', '#f47fa1'],
  },
  {
    id: 'yorha_light',
    name: '终端·纸',
    jpName: 'YORHA ARCHIVE',
    desc: '经典米灰纸张与炭墨高对比配色，与其余主题统一圆角语言',
    variant: 'light',
    swatches: ['#e6e1d3', '#efeadd', '#3b372e', '#9c4a3c'],
  },
]

export function mapLegacyTheme(id: string | undefined): ThemeId {
  switch (id) {
    case 'sora_light':
    case 'cloud_light':
      return 'sora_light'
    case 'washi_light':
    case 'paper_light':
      return 'washi_light'
    case 'tsukiyo_dark':
    case 'graphite_dark':
      return 'tsukiyo_dark'
    case 'yorha_light':
      return 'yorha_light'
    default:
      return 'sora_light'
  }
}
