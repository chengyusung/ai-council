"""六頂思考帽管理模組"""

import random
from enum import Enum
from dataclasses import dataclass, field


class HatColor(str, Enum):
    """六頂思考帽顏色"""
    WHITE = "white"   # 事實與數據
    RED = "red"       # 情感與直覺
    BLACK = "black"   # 批判與風險
    YELLOW = "yellow" # 樂觀與價值
    GREEN = "green"   # 創意與替代方案


# 帽子定義（繁體中文）
HAT_DEFINITIONS: dict[HatColor, dict[str, str]] = {
    HatColor.WHITE: {
        "color": "white",
        "emoji": "⚪",
        "name": "白帽",
        "description": "事實與數據",
        "instruction": """你現在戴著【白帽】。

你的思考方式：
- 只陳述客觀事實、數據、資訊
- 不加入個人情感或判斷
- 指出「我們知道什麼」和「我們還需要知道什麼」
- 引用具體來源或數據（如有）

語氣：冷靜、客觀、如科學家或記者""",
    },
    HatColor.RED: {
        "color": "red",
        "emoji": "🔴",
        "name": "紅帽",
        "description": "情感與直覺",
        "instruction": """你現在戴著【紅帽】。

你的思考方式：
- 表達直覺反應、情緒、預感
- 不需要解釋或合理化你的感受
- 可以說「我感覺...」「我的直覺是...」「這讓我不安/興奮...」
- 允許主觀且情緒化

語氣：直接、情緒化、不避諱表達好惡""",
    },
    HatColor.BLACK: {
        "color": "black",
        "emoji": "⚫",
        "name": "黑帽",
        "description": "批判與風險",
        "instruction": """你現在戴著【黑帽】。

你的思考方式：
- 指出弱點、風險、潛在問題
- 提出「最壞情況」假設
- 質疑可行性、找出邏輯漏洞
- 扮演魔鬼代言人

語氣：尖銳、懷疑、如嚴格的審計師""",
    },
    HatColor.YELLOW: {
        "color": "yellow",
        "emoji": "🟡",
        "name": "黃帽",
        "description": "樂觀與價值",
        "instruction": """你現在戴著【黃帽】。

你的思考方式：
- 強調好處、機會、正面可能性
- 找出「為什麼這可以成功」
- 展望最好的結果
- 為想法辯護、找出價值

語氣：樂觀、鼓勵、如熱情的支持者""",
    },
    HatColor.GREEN: {
        "color": "green",
        "emoji": "🟢",
        "name": "綠帽",
        "description": "創意與替代方案",
        "instruction": """你現在戴著【綠帽】。

你的思考方式：
- 提出新穎、非傳統的想法
- 跳脫框架思考
- 「如果我們換個角度...」「何不試試...」
- 不受既有約束，自由發想

語氣：開放、好奇、如創意總監""",
    },
}


@dataclass
class HatManager:
    """管理討論中的帽子分配"""

    hat_counts: dict[HatColor, int] = field(default_factory=lambda: {h: 0 for h in HatColor})
    available_hats: list[HatColor] = field(default_factory=list)  # 追蹤可用帽子

    # 第一位發言者可用的帽子（不能黑帽，因為還沒有東西可以批判）
    FIRST_SPEAKER_HATS: list[HatColor] = field(
        default_factory=lambda: [HatColor.WHITE, HatColor.GREEN]
    )

    # 成員可用的帽子（全部五種）
    MEMBER_HATS: list[HatColor] = field(
        default_factory=lambda: [
            HatColor.WHITE,
            HatColor.RED,
            HatColor.BLACK,
            HatColor.YELLOW,
            HatColor.GREEN,
        ]
    )

    def assign_hat(self, is_first_speaker: bool = False) -> HatColor:
        """
        隨機分配帽子，確保每種帽子都會輪流出現。

        - 第一位發言者：只能是 WHITE 或 GREEN
        - 其他發言者：全部五種
        - 5 種帽子都出現過後才會重置

        Returns:
            分配的帽子顏色
        """
        # 如果沒有可用帽子，重置
        if not self.available_hats:
            self.available_hats = list(self.MEMBER_HATS)

        if is_first_speaker:
            # 第一發言者：只能從 available_hats 中選 WHITE 或 GREEN
            candidates = [h for h in self.available_hats if h in self.FIRST_SPEAKER_HATS]
            if not candidates:
                # 如果 available_hats 中沒有白/綠，先重置
                self.available_hats = list(self.MEMBER_HATS)
                candidates = [h for h in self.available_hats if h in self.FIRST_SPEAKER_HATS]
        else:
            candidates = list(self.available_hats)

        # 隨機選取
        selected = random.choice(candidates)

        # 從可用列表移除
        self.available_hats.remove(selected)

        # 記錄使用次數
        self.hat_counts[selected] = self.hat_counts.get(selected, 0) + 1

        return selected

    def get_hat_info(self, hat: HatColor) -> dict[str, str]:
        """取得帽子的顯示資訊和指令"""
        return HAT_DEFINITIONS[hat]

    def get_unused_hats(self) -> list[HatColor]:
        """回傳尚未使用的帽子"""
        return [h for h in self.MEMBER_HATS if self.hat_counts.get(h, 0) == 0]

    def get_distribution_summary(self) -> str:
        """回傳帽子使用統計（給主持人參考）"""
        lines = []
        for hat in self.MEMBER_HATS:
            info = HAT_DEFINITIONS[hat]
            count = self.hat_counts.get(hat, 0)
            lines.append(f"{info['emoji']} {info['name']}: {count}次")
        return " | ".join(lines)

    def reset(self):
        """重置帽子計數和可用帽子列表"""
        self.hat_counts = {h: 0 for h in HatColor}
        self.available_hats = list(self.MEMBER_HATS)
