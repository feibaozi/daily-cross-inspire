import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

THEMES = [
    {"name": "复制的艺术", "keywords": ["复制", "模仿", "仿生", "再现", "翻译"], "domains": ["演化生物学", "认知神经科学", "语言学"]},
    {"name": "看不见的连接", "keywords": ["网络", "纠缠", "关联", "共振", "同步"], "domains": ["量子物理", "气候科学", "海洋生物学"]},
    {"name": "时间的形状", "keywords": ["时间", "历史", "记忆", "衰变", "周期"], "domains": ["中世纪欧洲史", "古生物学", "天文学"]},
    {"name": "建造与毁灭", "keywords": ["建造", "结构", "崩塌", "重建", "韧性"], "domains": ["前卫建筑设计", "材料科学", "考古学"]},
    {"name": "意识的边界", "keywords": ["意识", "感知", "智能", "自我", "认知"], "domains": ["认知神经科学", "机器人学", "古代哲学"]},
    {"name": "声音与沉默", "keywords": ["声音", "音乐", "振动", "寂静", "共鸣"], "domains": ["音乐学", "量子物理", "语言学"]},
    {"name": "极端生存", "keywords": ["极端", "适应", "生存", "压力", "进化"], "domains": ["海洋生物学", "古生物学", "气候科学"]},
    {"name": "地图与领土", "keywords": ["地图", "空间", "导航", "边界", "探索"], "domains": ["天文学", "城市人类学", "中世纪欧洲史"]},
    {"name": "材料的秘密生活", "keywords": ["材料", "物质", "相变", "晶体", "纳米"], "domains": ["材料科学", "量子物理", "前卫建筑设计"]},
    {"name": "语言之外", "keywords": ["语言", "沟通", "符号", "沉默", "翻译"], "domains": ["语言学", "认知神经科学", "音乐学"]},
    {"name": "废墟中的未来", "keywords": ["废墟", "遗迹", "重建", "遗产", "遗忘"], "domains": ["考古学", "中世纪欧洲史", "前卫建筑设计"]},
    {"name": "计算的自然", "keywords": ["计算", "算法", "自然", "涌现", "复杂"], "domains": ["机器人学", "演化生物学", "量子物理"]},
]


class ThemeEngine:
    def __init__(self, cache_db_path: str = "data/cache.db"):
        self.cache_db_path = cache_db_path
        self._init_db()

    def _init_db(self):
        import sqlite3
        import os
        os.makedirs(os.path.dirname(self.cache_db_path), exist_ok=True)
        conn = sqlite3.connect(self.cache_db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS theme_history ("
            "  month TEXT PRIMARY KEY,"
            "  theme_name TEXT NOT NULL,"
            "  keywords TEXT,"
            "  domains TEXT"
            ")"
        )
        conn.close()

    def get_current_theme(self) -> Optional[dict]:
        now = datetime.now()
        month_key = f"{now.year}-{now.month:02d}"

        import sqlite3
        conn = sqlite3.connect(self.cache_db_path)
        row = conn.execute(
            "SELECT theme_name, keywords, domains FROM theme_history WHERE month = ?",
            (month_key,)
        ).fetchone()
        conn.close()

        if row:
            return {
                "name": row[0],
                "keywords": json.loads(row[1]) if row[1] else [],
                "domains": json.loads(row[2]) if row[2] else [],
            }

        used = self._get_used_themes()
        available = [t for t in THEMES if t["name"] not in used]

        if not available:
            available = THEMES

        import random
        theme = random.choice(available)

        conn = sqlite3.connect(self.cache_db_path)
        conn.execute(
            "INSERT OR REPLACE INTO theme_history (month, theme_name, keywords, domains) VALUES (?, ?, ?, ?)",
            (month_key, theme["name"], json.dumps(theme["keywords"], ensure_ascii=False),
             json.dumps(theme["domains"], ensure_ascii=False))
        )
        conn.commit()
        conn.close()

        logger.info(f"Theme for {month_key}: {theme['name']}")
        return theme

    def _get_used_themes(self) -> list[str]:
        import sqlite3
        conn = sqlite3.connect(self.cache_db_path)
        rows = conn.execute("SELECT theme_name FROM theme_history").fetchall()
        conn.close()
        return [r[0] for r in rows]

    def get_theme_boost_domains(self) -> list[str]:
        theme = self.get_current_theme()
        if theme:
            return theme.get("domains", [])
        return []

    def get_theme_header(self) -> str:
        theme = self.get_current_theme()
        if not theme:
            return ""

        keywords = " · ".join(theme["keywords"][:4])
        return f"## 📚 本月主题：{theme['name']}\n\n> 关键词：{keywords}\n\n---\n\n"