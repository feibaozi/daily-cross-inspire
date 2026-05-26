# 📰 DailyCrossInspire — 每日跨界灵感早报

> 一个全自动的跨学科知识简报生成器。每天从 15 个不同学科领域采集文章，用 AI 翻译成通俗中文摘要，推送到飞书/钉钉/邮件。

---

## 核心理念

> **"你不会在量子物理课上听到中世纪的八卦，但我们帮你把这两件事连起来了。"**

大多数信息推送工具让你困在信息茧房里。DailyCrossInspire 刻意从**毫无关联的学科**中挑选文章，用 AI 找到它们之间的隐秘联系——让物理学家知道 14 世纪发生了什么，让音乐家了解黑洞的最新发现。

---

## 功能全景

```
每日自动化流水线 (UTC 23:00 / 北京时间 07:00)
│
├── 📡 RSS 采集 ── 15 个领域，并行抓取，去重缓存
├── 🎯 智能选择 ── 偏好加权随机选取 3 篇
├── 🤖 AI 摘要 ── DeepSeek 生成中文摘要 + 跨界知识连接
├── 🏷️ 自动标签 ── AI 为每篇文章生成 3 个标签
├── 🔬 深度解读 ── 可折叠的背景/原理/影响分析
├── 📖 历史上的今天 ── Wikipedia API 历史事件
├── 🎭 月度主题 ── 每月轮换跨学科主题
├── 🎙️ 播客脚本 ── AI 生成 5 分钟播客 + TTS 语音
├── 📊 阅读画像 ── 基于反馈的读者知识图谱
│
├── 🆕 v3.0 新功能
│   ├── 💬 AI 对话管家 ── 可对话的知识伙伴，引用近期阅读上下文
│   ├── 🌌 知识星系图 ── D3.js 力导向图，可视化你的知识探索轨迹
│   └── 🏠 茧房检测 ── 情绪追踪 + 反茧房算法，防止形成新的信息茧房
│
├── 📝 报告合成 ── Markdown + 飞书卡片 JSON
├── 📨 多渠道推送 ── 飞书 / 钉钉 / 邮件
├── 🌐 静态站点 ── GitHub Pages 归档搜索页
└── 📅 周日精选 ── 每周特刊
```

---

## 覆盖领域（15 个）

| 领域 | 来源 |
|------|------|
| 🔬 量子物理 | Physics World - Quantum |
| 🏰 中世纪欧洲史 | Medievalists.net |
| 🎨 当代艺术 | Artsy - Contemporary |
| 🌍 人类学 | SAPIENS Magazine |
| 🌊 海洋生物学 | Oceanographic Magazine |
| 🧠 认知科学 | Cognitive Science Society |
| 🎵 音乐学 | Classical Music News |
| 🌋 地质学 | USGS Earthquake Hazards |
| 🦠 微生物学 | Nature Microbiology |
| 🌾 农业科技 | Modern Farmer |
| 📐 数学 | Quanta Magazine - Math |
| 🏛️ 考古学 | Archaeology Magazine |
| 🧬 遗传学 | GenomeWeb |
| 💻 计算机科学 | MIT CSAIL News |
| 🎭 戏剧与表演艺术 | American Theatre |

---

## 快速开始

### 环境变量

```bash
# 必填
DEEPSEEK_API_KEY=sk-xxx     # DeepSeek API Key

# 推送渠道（至少配一个）
FEISHU_WEBHOOK_URL=https://open.feishu.cn/xxx
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/xxx
EMAIL_SENDER=your@email.com
EMAIL_PASSWORD=your_password
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_RECIPIENT=recipient@email.com
```

### 本地运行

```bash
pip install -r requirements.txt
# 可选: pip install edge-tts (播客语音合成)
python main.py
```

### 启动 AI 对话管家

```bash
pip install fastapi uvicorn
python chat_api.py
# 访问 http://localhost:8080
# 聊天页面: site/chat.html
```

### Docker

```bash
docker build -t daily-cross-inspire .
docker run \
  -e DEEPSEEK_API_KEY=sk-xxx \
  -e FEISHU_WEBHOOK_URL=https://open.feishu.cn/xxx \
  daily-cross-inspire
```

### GitHub Actions（生产部署）

项目已配置 `.github/workflows/daily-report.yml`：
- 每天北京时间 07:00 自动运行
- 生成静态站点并部署到 GitHub Pages
- 在仓库 Settings → Secrets 中配置环境变量

---

## 项目结构

```
daily-cross-inspire/
├── main.py                    # 入口，编排完整流水线
├── chat_api.py                # AI 对话管家 API 服务 (FastAPI)
├── src/
│   ├── collector.py           # RSS 采集器（feedparser + httpx）
│   ├── selector.py            # 领域选择器（偏好加权随机）
│   ├── ai_summarizer.py       # AI 摘要生成（DeepSeek API）
│   ├── composer.py            # 报告合成（Markdown + 飞书卡片）
│   ├── pusher.py              # 推送器（飞书/钉钉/邮件）
│   ├── preference.py          # 偏好引擎（点赞/跳过反馈）
│   ├── deep_dive.py           # 深度解读 + 自动标签
│   ├── weekly.py              # 周日精选特刊
│   ├── podcast.py             # 播客脚本生成 + TTS
│   ├── reading_profile.py     # 阅读画像 + 邻近领域推荐
│   ├── theme_engine.py        # 月度主题引擎
│   ├── on_this_day.py         # 历史上的今天
│   ├── static_site.py         # 静态站点生成
│   ├── media_collector.py     # YouTube 字幕采集（实验性）
│   ├── chat_engine.py         # AI 对话引擎（上下文记忆）
│   ├── echo_chamber.py        # 茧房检测 + 情绪追踪
│   └── galaxy.py              # 知识星系图数据导出
├── config/
│   ├── sources.yaml           # 15 个 RSS 源配置
│   └── settings.yaml          # 运行时配置（AI/推送/缓存）
├── data/
│   └── cache.db               # SQLite（去重/偏好/归档/情绪/对话）
├── site/
│   ├── index.html             # 搜索归档页面
│   ├── feedback.html          # 反馈收集页面
│   ├── emotion.html           # 情绪反馈页面
│   ├── chat.html              # AI 对话管家页面
│   ├── galaxy.html            # 知识星系图可视化
│   └── galaxy_data.json       # 星系图数据（自动生成）
├── .github/workflows/
│   └── daily-report.yml       # GitHub Actions 自动调度
├── Dockerfile
├── requirements.txt
└── .gitignore
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| 语言 | Python 3.11+ |
| RSS 解析 | feedparser + httpx |
| AI 模型 | DeepSeek-V3 |
| 数据库 | SQLite (去重/偏好/归档/情绪/对话) |
| HTML 清洗 | BeautifulSoup4 + lxml |
| 对话 API | FastAPI + uvicorn |
| 配置 | YAML (环境变量注入) |
| 容器化 | Docker |
| CI/CD | GitHub Actions |
| 静态站点 | 纯 HTML + JS (部署到 GitHub Pages) |
| 星系图 | D3.js v7 (力导向图) |
| 播客 TTS | edge-tts（可选） |

---

## 开发进度

```
██████████████████████████████░░  95%
```

| 功能 | 状态 | 版本 |
|------|------|------|
| RSS 多源采集 | ✅ | v1.0 |
| 去重缓存 + 健康监控 | ✅ | v1.0 |
| AI 摘要 + 跨界连接 | ✅ | v1.0 |
| 飞书/钉钉/邮件推送 | ✅ | v1.0 |
| 周日精选特刊 | ✅ | v1.0 |
| 静态站点 + 搜索归档 | ✅ | v1.0 |
| Docker + CI/CD | ✅ | v1.0 |
| 偏好引擎（点赞/跳过反馈） | ✅ | v2.0 |
| 深度解读 + 自动标签 | ✅ | v2.0 |
| 历史上的今天 | ✅ | v2.0 |
| 月度主题引擎 | ✅ | v2.0 |
| 播客脚本 + TTS | ✅ | v2.0 |
| 阅读画像 | ✅ | v2.0 |
| 💬 AI 对话管家 | ✅ | v3.0 |
| 🌌 知识星系图 | ✅ | v3.0 |
| 🏠 茧房检测 + 情绪追踪 | ✅ | v3.0 |
| 播客音频自动推送 | ⬜ | - |
| Web 管理面板 | ⬜ | - |
| AI 辩论赛 | ⬜ | - |
| 自愈式 RSS 网络 | ⬜ | - |