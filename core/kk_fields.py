"""Parameter 块里布尔字典字段（提问 / 特点 / H相关）的中文标签映射。

这些字段在卡片里是 {内部名: bool} 的字典。KK 与 KKS 的项目数不同，本模块给出
中文标签；遇到未收录的内部名一律回退显示原始名，绝不丢字段。`ExtendedSaveData`
是 KKEx 的占位键，展示时跳过、写回时保留。
"""

from __future__ import annotations

SKIP_KEYS = {"ExtendedSaveData"}

# 提问（awnser）—— 与游戏角色卡编辑界面一一对应
ANSWER_LABELS = {
    "animal": "喜欢小动物",
    "eat": "喜欢美食",
    "cook": "擅长料理",
    "exercise": "擅长运动",
    "study": "擅长学习",
    "fashionable": "擅长化妆",
    "blackCoffee": "喜欢无糖咖啡",
    "spicy": "喜欢吃辣",
    "sweet": "喜欢甜食",
}

# H 接受项（denial）
DENIAL_LABELS = {
    "kiss": "接吻",
    "aibu": "爱抚",
    "anal": "肛交",
    "massage": "按摩",
    "notCondom": "无套",
}

# 特点（attribute）—— 含 KK 与 KKS 两套（取并集），尽力翻译
ATTRIBUTE_LABELS = {
    "hinnyo": "频尿",
    "harapeko": "大胃王",
    "donkan": "迟钝",
    "choroi": "单纯好骗",
    "bitch": "淫荡",
    "mutturi": "闷骚",
    "dokusyo": "爱读书",
    "ongaku": "爱音乐",
    "kappatu": "活泼",
    "ukemi": "被动",
    "friendly": "友善",
    "kireizuki": "爱干净",
    "taida": "懒散",
    "sinsyutu": "积极进取",
    "hitori": "喜欢独处",
    "undo": "爱运动",
    "majime": "认真",
    "likeGirls": "喜欢女生",
    # KKS 追加
    "okute": "晚熟",
    "active": "主动",
    "info": "消息灵通",
    "love": "恋爱脑",
    "talk": "健谈",
    "nakama": "重视伙伴",
    "nonbiri": "悠闲",
    "lonely": "怕寂寞",
}

# Parameter 里的标量字段中文标签，用于"卡片详情"表
SCALAR_LABELS = {
    "lastname": "姓",
    "firstname": "名",
    "nickname": "昵称",
    "sex": "性别",
    "personality": "性格",
    "bloodType": "血型",
    "birthMonth": "生月",
    "birthDay": "生日",
    "clubActivities": "社团",
    "weakPoint": "敏感部位(索引)",
    "aggressive": "积极性",
    "diligence": "勤奋",
    "kindness": "温柔",
    "voiceRate": "声音音调",
    "exType": "扩展类型",
    "callType": "称呼类型",
    "version": "数据版本",
}


def label_for(key: str, mapping: dict[str, str]) -> str:
    return mapping.get(key, key)


def count_true(d: dict | None) -> tuple[int, int]:
    """返回 (勾选数, 总项数)，跳过 ExtendedSaveData 占位键。"""
    if not isinstance(d, dict):
        return (0, 0)
    items = [(k, v) for k, v in d.items() if k not in SKIP_KEYS]
    checked = sum(1 for _, v in items if v is True)
    return (checked, len(items))


def editable_items(d: dict | None) -> list[tuple[str, bool]]:
    """返回可编辑的 (key, 当前bool) 列表，跳过占位键与非布尔项。"""
    if not isinstance(d, dict):
        return []
    out = []
    for k, v in d.items():
        if k in SKIP_KEYS:
            continue
        if isinstance(v, bool):
            out.append((k, v))
    return out
