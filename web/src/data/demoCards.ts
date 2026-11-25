import type { CardDetail, CardSummary } from '../types/kk'

/**
 * 生成日系清新二次元档案卡矢量封面（仅用于「预览样例」模式，当用户尚未选择本地角色卡目录时展示完整画廊质感）。
 * 选中本地目录后会直接渲染硬盘中的真实 PNG 角色卡立绘。
 */
function makeAnimeCardArt(opts: {
  code: string
  jpTitle: string
  subTitle: string
  bgTop: string
  bgBottom: string
  accent: string
  halo: string
  hair: string
  eye: string
  ribbon: string
  uniform: string
  style?: 'sky' | 'sakura' | 'dusk' | 'mint' | 'amber' | 'violet'
}): string {
  const { code, jpTitle, subTitle, bgTop, bgBottom, accent, halo, ribbon } = opts
  const kanji = jpTitle.slice(0, 1)
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 504 704" width="504" height="704">
    <defs>
      <linearGradient id="bg" x1="0" y1="0" x2="0.4" y2="1">
        <stop offset="0%" stop-color="${bgTop}"/>
        <stop offset="68%" stop-color="${bgBottom}"/>
        <stop offset="100%" stop-color="#ffffff"/>
      </linearGradient>
      <linearGradient id="stripe" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#ffffff" stop-opacity="0.58"/>
        <stop offset="100%" stop-color="${accent}" stop-opacity="0.06"/>
      </linearGradient>
      <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
        <path d="M 24 0 L 0 0 0 24" fill="none" stroke="#ffffff" stroke-opacity="0.32" stroke-width="1"/>
      </pattern>
    </defs>
    <rect width="504" height="704" fill="url(#bg)"/>
    <rect width="504" height="704" fill="url(#grid)"/>

    <!-- 日系学院档案风光学几何构图 -->
    <path d="M 0 420 L 504 330 L 504 704 L 0 704 Z" fill="#ffffff" fill-opacity="0.72"/>
    <circle cx="252" cy="285" r="154" fill="#ffffff" fill-opacity="0.30"/>
    <circle cx="252" cy="285" r="126" fill="none" stroke="#ffffff" stroke-opacity="0.82" stroke-width="2"/>
    <circle cx="252" cy="285" r="102" fill="none" stroke="${accent}" stroke-opacity="0.35" stroke-width="1.5" stroke-dasharray="7 6"/>
    <!-- 倾斜光环 -->
    <ellipse cx="252" cy="285" rx="176" ry="44" fill="none" stroke="${halo}" stroke-width="3.5" transform="rotate(-18 252 285)"/>
    <ellipse cx="252" cy="285" rx="146" ry="30" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-opacity="0.9" transform="rotate(14 252 285)"/>
    <!-- 中心大号日系印刷汉字徽标 -->
    <text x="252" y="330" text-anchor="middle" font-family="Noto Serif JP, Noto Serif SC, serif" font-size="132" font-weight="700" fill="${accent}" fill-opacity="0.88">${kanji}</text>
    <!-- 菱形装饰点 -->
    <polygon points="252,118 260,128 252,138 244,128" fill="#ffffff" fill-opacity="0.95"/>
    <polygon points="396,232 403,240 396,248 389,240" fill="${ribbon}" fill-opacity="0.9"/>
    <polygon points="108,334 114,341 108,348 102,341" fill="${accent}" fill-opacity="0.75"/>

    <!-- 光泽罩层与画册细线框 -->
    <rect width="504" height="704" fill="url(#stripe)"/>
    <rect x="20" y="20" width="464" height="664" rx="16" fill="none" stroke="#ffffff" stroke-opacity="0.75" stroke-width="1.5"/>

    <!-- 顶部索引编号 -->
    <text x="40" y="58" font-family="Bahnschrift, sans-serif" font-size="15" font-weight="700" letter-spacing="2.4" fill="#ffffff" fill-opacity="0.95">${code}</text>
    <text x="464" y="58" text-anchor="end" font-family="Bahnschrift, sans-serif" font-size="13" font-weight="600" letter-spacing="1.4" fill="#ffffff" fill-opacity="0.9">${subTitle}</text>

    <!-- 底部杂志感档案签 -->
    <line x1="40" y1="564" x2="464" y2="564" stroke="${accent}" stroke-opacity="0.28" stroke-width="1.5"/>
    <rect x="40" y="582" width="44" height="4" rx="2" fill="${ribbon}"/>
    <text x="40" y="628" font-family="Noto Serif JP, Noto Serif SC, serif" font-size="30" font-weight="700" fill="#14233b">${jpTitle}</text>
    <text x="40" y="656" font-family="Bahnschrift, sans-serif" font-size="12" letter-spacing="2.2" fill="#4f6482">KOIKATU ARCHIVE · SAMPLE CARD</text>
    <!-- 右下极简条码纹 -->
    <g fill="${accent}" fill-opacity="0.45">
      <rect x="412" y="608" width="3" height="44"/>
      <rect x="419" y="608" width="6" height="44"/>
      <rect x="429" y="608" width="2" height="44"/>
      <rect x="435" y="608" width="5" height="44"/>
      <rect x="444" y="608" width="3" height="44"/>
      <rect x="451" y="608" width="7" height="44"/>
      <rect x="461" y="608" width="3" height="44"/>
    </g>
  </svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

export const DEMO_CARDS: CardSummary[] = [
  {
    id: 'demo-sora',
    path: 'demo://Arona_Sora_KKS.png',
    fileName: 'Arona_Sora_KKS.png',
    type: 'character',
    game: 'KKS',
    name: '青空 璃奈',
    author: '晴空画室',
    authorSource: 'card',
    subtitle: '晴空水手服 · 示范卡',
    personalityLabel: '活泼',
    bloodType: 'O',
    birthday: '07月14日',
    modCount: 12,
    fileSizeText: '286 KB',
    isDemo: true,
    thumbnailUrl: makeAnimeCardArt({
      code: 'ARCHIVE · 01',
      jpTitle: '青空 璃奈',
      subTitle: 'KKS / CHARA',
      bgTop: '#4aa3ff',
      bgBottom: '#d9eeff',
      accent: '#1a73e8',
      halo: '#63d2ff',
      hair: '#69b8ff',
      eye: '#1c65c9',
      ribbon: '#ff7fa3',
      uniform: '#1e5ec7',
    }),
  },
  {
    id: 'demo-sakura',
    path: 'demo://Sakuragi_Hina_KK.png',
    fileName: 'Sakuragi_Hina_KK.png',
    type: 'character',
    game: 'KK',
    name: '樱木 雏乃',
    author: '樱花工房',
    authorSource: 'card',
    subtitle: '春日针织开衫 · 示范卡',
    personalityLabel: '温柔',
    bloodType: 'A',
    birthday: '04月02日',
    modCount: 8,
    fileSizeText: '241 KB',
    isDemo: true,
    thumbnailUrl: makeAnimeCardArt({
      code: 'ARCHIVE · 02',
      jpTitle: '桜木 雛乃',
      subTitle: 'KK / CHARA',
      bgTop: '#ff9ebb',
      bgBottom: '#fff1f5',
      accent: '#e0527c',
      halo: '#ff7fa8',
      hair: '#f4a8c0',
      eye: '#b94473',
      ribbon: '#3b82f6',
      uniform: '#485b8a',
    }),
  },
  {
    id: 'demo-tsuki',
    path: 'demo://Shirogane_Kei_KKS.png',
    fileName: 'Shirogane_Kei_KKS.png',
    type: 'character',
    game: 'KKS',
    name: '白银 凯伊',
    author: '千年制作部',
    authorSource: 'card',
    subtitle: '千年学院制服 · 示范卡',
    personalityLabel: '认真',
    bloodType: 'AB',
    birthday: '11月19日',
    modCount: 19,
    fileSizeText: '318 KB',
    isDemo: true,
    thumbnailUrl: makeAnimeCardArt({
      code: 'ARCHIVE · 03',
      jpTitle: '白銀 ケイ',
      subTitle: 'KKS / CHARA',
      bgTop: '#6c8ebf',
      bgBottom: '#e7eef8',
      accent: '#335c9c',
      halo: '#8cc4ff',
      hair: '#c9d6e8',
      eye: '#3461a8',
      ribbon: '#4da3ff',
      uniform: '#283956',
    }),
  },
  {
    id: 'demo-coord',
    path: 'demo://Summer_Sailor_Coord.png',
    fileName: 'Summer_Sailor_Coord.png',
    type: 'coordinate',
    game: '?',
    name: '夏晴水手套装',
    author: '晴空画室',
    authorSource: 'card',
    subtitle: '独立服装卡 · 示范卡',
    personalityLabel: '服装配置',
    modCount: 5,
    fileSizeText: '134 KB',
    isDemo: true,
    thumbnailUrl: makeAnimeCardArt({
      code: 'COORD · 04',
      jpTitle: '夏晴 セーラー',
      subTitle: 'COORD / 通用',
      bgTop: '#4ac7b5',
      bgBottom: '#e5faf6',
      accent: '#189684',
      halo: '#7ae8d7',
      hair: '#52b8a8',
      eye: '#1c7c70',
      ribbon: '#ff8a65',
      uniform: '#1d6f7a',
    }),
  },
  {
    id: 'demo-kohaku',
    path: 'demo://Kohaku_Mika_KK.png',
    fileName: 'Kohaku_Mika_KK.png',
    type: 'character',
    game: 'KK',
    name: '琥珀 美佳',
    author: '千年制作部',
    authorSource: 'card',
    subtitle: '午后露台常服 · 示范卡',
    personalityLabel: '傲娇',
    bloodType: 'B',
    birthday: '09月28日',
    modCount: 14,
    fileSizeText: '274 KB',
    isDemo: true,
    thumbnailUrl: makeAnimeCardArt({
      code: 'ARCHIVE · 05',
      jpTitle: '琥珀 ミカ',
      subTitle: 'KK / CHARA',
      bgTop: '#f5b864',
      bgBottom: '#fff6e6',
      accent: '#d97706',
      halo: '#ffd080',
      hair: '#e8b66c',
      eye: '#b56318',
      ribbon: '#e0527c',
      uniform: '#4b5563',
    }),
  },
  {
    id: 'demo-scene',
    path: 'demo://Classroom_Sunset_Scene.png',
    fileName: 'Classroom_Sunset_Scene.png',
    type: 'scene',
    game: 'KKS',
    name: '放课后晴空教室',
    subtitle: '双人工作室场景 · 示范卡',
    personalityLabel: '场景卡',
    modCount: 23,
    fileSizeText: '1.42 MB',
    isDemo: true,
    thumbnailUrl: makeAnimeCardArt({
      code: 'SCENE · 06',
      jpTitle: '放課後の教室',
      subTitle: 'KKS / SCENE',
      bgTop: '#7a88e8',
      bgBottom: '#eef0ff',
      accent: '#4f5fd4',
      halo: '#b2bcff',
      hair: '#8795e0',
      eye: '#424fa8',
      ribbon: '#ff85a2',
      uniform: '#353e78',
    }),
  },
]

export function makeDemoDetail(card: CardSummary): CardDetail {
  const parts = card.name.split(' ')
  const lastname = parts[0] || card.name
  const firstname = parts[1] || ''
  return {
    path: card.path,
    fileName: card.fileName,
    game: card.game,
    gameName: card.game === 'KKS' ? 'Koikatu Sunshine / 恋活日光浴' : 'Koikatu / 恋活',
    marker: card.game === 'KKS' ? '【KoiKatuCharaSun】' : '【KoiKatuChara】',
    version: '0.0.0',
    author: card.author || '',
    authorSource: card.authorSource || '',
    thumbnailUrl: card.thumbnailUrl,
    faceUrl: card.thumbnailUrl,
    isDemo: true,
    parameter: {
      lastname,
      firstname,
      nickname: firstname || lastname,
      sex: 1,
      personality: card.id === 'demo-sora' ? 10 : card.id === 'demo-sakura' ? 9 : card.id === 'demo-tsuki' ? 5 : 6,
      bloodType: card.id === 'demo-sora' ? 2 : card.id === 'demo-sakura' ? 0 : card.id === 'demo-tsuki' ? 3 : 1,
      birthMonth: card.id === 'demo-sora' ? 7 : card.id === 'demo-sakura' ? 4 : card.id === 'demo-tsuki' ? 11 : 9,
      birthDay: card.id === 'demo-sora' ? 14 : card.id === 'demo-sakura' ? 2 : card.id === 'demo-tsuki' ? 19 : 28,
      clubActivities: '游戏开发部',
      voiceRate: 0.56,
      awnser: {
        animal: true,
        eat: true,
        cook: card.id === 'demo-sakura',
        exercise: card.id === 'demo-sora',
        study: card.id === 'demo-tsuki',
        fashionable: true,
        blackCoffee: card.id === 'demo-tsuki',
        spicy: false,
        sweet: true,
      },
      attribute: {
        hinnyo: false,
        harapeko: card.id === 'demo-sora',
        donkan: false,
        choroi: false,
        bitch: false,
        mutturi: card.id === 'demo-kohaku',
        dokusyo: card.id === 'demo-tsuki',
        ongaku: true,
        kappatu: card.id === 'demo-sora',
        ukemi: false,
        friendly: true,
        kireizuki: true,
        taida: false,
        sinsyutu: card.id === 'demo-tsuki',
        hitori: false,
        undo: card.id === 'demo-sora',
        majime: card.id === 'demo-tsuki',
        likeGirls: false,
        okute: card.id === 'demo-sakura',
        active: card.id === 'demo-sora',
        info: true,
        love: false,
        talk: true,
        nakama: true,
        nonbiri: card.id === 'demo-sakura',
        lonely: false,
      },
      denial: {
        kiss: true,
        aibu: true,
        anal: false,
        massage: true,
        notCondom: false,
      },
      rawScalars: {
        lastname,
        firstname,
        nickname: firstname || lastname,
        sex: 1,
        personality: card.personalityLabel || '活泼',
        bloodType: card.bloodType || 'O',
        clubActivities: '游戏开发部',
        voiceRate: 0.56,
        version: '0.0.5',
      },
    },
    modIds: [
      'com.kktools.demo.hair_sora_pack',
      'com.kktools.demo.sailor_uniform_v2',
      'com.kktools.demo.eye_highlight_clear',
      'com.kktools.demo.halo_accessories',
    ],
    blockNames: ['Custom', 'Coordinate', 'Parameter', 'Status', 'KKEx'],
  }
}
