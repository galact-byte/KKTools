"""恋活 / 恋活日光浴 角色卡里枚举字段的友好名称映射。

注意：性格、社团等枚举在装了 mod 后会扩展，数值并不固定。这里只内置**基础游戏**
的常见取值，做尽力而为的展示；遇到未知数值一律回退成 "未知(<数值>)"，绝不报错。
字段若本身就是字符串（部分卡片社团直接存名字），则原样显示。
"""

from __future__ import annotations

# 血型：基础游戏顺序 A / B / O / AB
BLOOD_TYPES = ["A", "B", "O", "AB"]

# 性格（基础恋活，索引 -> 名称）。装了性格 mod 后会有更多，未知则回退。
KK_PERSONALITIES = {
    0: "冷静",
    1: "天真",
    2: "高傲",
    3: "纯朴",
    4: "无口",
    5: "认真",
    6: "傲娇",
    7: "妹系",
    8: "姐系",
    9: "温柔",
    10: "活泼",
    11: "文静",
    12: "腹黑",
    13: "病娇",
    14: "中二",
    15: "天然",
    16: "诱惑",
    17: "怪异",
}

# 恋活日光浴性格表与恋活略有差异，这里复用基础项并允许回退。
KKS_PERSONALITIES = dict(KK_PERSONALITIES)


def blood_type_name(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int) and 0 <= value < len(BLOOD_TYPES):
        return BLOOD_TYPES[value]
    return f"未知({value})"


def personality_name(value, game: str = "KK") -> str:
    if isinstance(value, str):
        return value
    table = KKS_PERSONALITIES if game == "KKS" else KK_PERSONALITIES
    if isinstance(value, int) and value in table:
        return table[value]
    return f"未知({value})"


def personality_choices(game: str = "KK") -> list[tuple[int, str]]:
    table = KKS_PERSONALITIES if game == "KKS" else KK_PERSONALITIES
    return [(idx, f"{idx:02d} - {name}") for idx, name in sorted(table.items())]


# Parameter 块里常见的人类可读字段 -> 中文标签，用于"卡片详情"展示。
PARAMETER_LABELS = {
    "lastname": "姓",
    "firstname": "名",
    "nickname": "昵称",
    "fullname": "完整名",
    "sex": "性别",
    "personality": "性格",
    "bloodType": "血型",
    "birthMonth": "生月",
    "birthDay": "生日",
    "clubActivities": "社团",
    "weight": "体重",
}
