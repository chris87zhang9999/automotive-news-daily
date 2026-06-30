# Design: automotive-news-daily

**Date:** 2026-06-29  
**Status:** Approved

## Problem

需要一个每日自动采集全球汽车行业新闻的系统，重点关注：
- 中国品牌出海（尤其理想汽车在欧洲、中东、俄罗斯、中亚、东南亚的动态）
- 理想汽车质量表现（召回、缺陷、消费者投诉）
- 全球主流品牌动态

每天至少 30 条，用智谱 GLM-4-flash 生成 100 词英文摘要，通过飞书群机器人 webhook 每日推送。

## Architecture

### Stack

- **Runtime:** Python 3.12 + uv（与 humanoid-tech-ops 同模式）
- **Scheduling:** GitHub Actions cron `0 1 * * *`（北京时间 09:00）
- **LLM:** 智谱 GLM-4-flash（OpenAI 兼容协议，复用现有 key）
- **Delivery:** 飞书群机器人 webhook（与 humanoid-tech-ops 同群）
- **Storage:** Git repo `reports/YYYY-MM-DD.md` + `data/seen.json`（去重窗口）

### Project Structure

```
automotive-news-daily/
├── src/
│   ├── collectors/
│   │   ├── base.py          # BaseCollector ABC
│   │   ├── rss.py           # 通用 RSS（feedparser）
│   │   ├── samr.py          # 中国 SAMR 缺陷产品召回 XML
│   │   ├── rapex.py         # EU Safety Gate 每周 XML 下载
│   │   ├── kba.py           # 德国 KBA 召回 CSV 下载
│   │   └── feeds.py         # 全部 Feed URL（按地区分组，~65条）
│   ├── filter.py            # 多语言关键词过滤 + 优先级打分
│   ├── dedup.py             # URL hash 去重（3天滑动窗口）
│   ├── summarizer.py        # GLM-4-flash 并发摘要（100词英文）
│   ├── delivery/
│   │   └── feishu.py        # 飞书 Bot webhook 卡片构建 + 分批发送
│   ├── config.py
│   └── schemas.py           # NewsItem dataclass
├── entrypoints/
│   └── collect_daily.py     # 主入口
├── data/
│   └── seen.json            # 去重窗口（git 提交，每日更新）
├── reports/
│   └── YYYY-MM-DD.md        # 每日完整报告
├── .github/workflows/
│   └── collect-daily.yml
├── pyproject.toml
├── .env.example
└── tests/
```

### Data Flow

```
65 RSS Feeds + SAMR XML + EU RAPEX XML + KBA CSV
        ↓ 并发拉取（feedparser / httpx）
   原始条目 ~300-600 条/天
        ↓ filter.py：多语言关键词命中 + 优先级打分
   汽车相关条目 ~80-120 条
        ↓ dedup.py：URL hash 去重（3天窗口）
   新条目 ~40-60 条
        ↓ 按优先级取 Top 35
        ↓ summarizer.py：并发调 GLM-4-flash（max_workers=5）
   35条 × 100词英文摘要（约 2-3 分钟）
        ↓
   保存 reports/YYYY-MM-DD.md + 更新 data/seen.json
        ↓ git commit + push
        ↓ feishu.py：按 P0→P1→P2→P3 分区推送卡片
```

## News Sources (~65 RSS Feeds)

### 全球/综合（10条）
- Reuters Business News
- Bloomberg Technology RSS
- Automotive News (automotiveneews.com)
- Motor1.com /rss/news/all
- InsideEVs
- Electrek
- Car and Driver
- WardsAuto
- TechCrunch (transport tag)
- The Verge (transportation)

### 中国品牌 + 理想专项（12条）
- 新浪汽车
- 懂车帝
- 汽车之家
- 36kr 汽车
- 第一财经汽车
- 电动汽车时代
- 路透中文
- 理想汽车官网新闻室
- 理想汽车 IR 投资者关系
- 华尔街见闻汽车
- 腾讯汽车
- 盖世汽车

### 欧洲（12条）
- Auto Motor und Sport（德）
- AutoBild（德）
- Heise Autos（德）
- Autocar UK
- Motor1 UK
- BBC Business
- Turbo.fr（法）
- Motor1 Italia
- Auto Express UK
- Driving Electric UK
- Car Magazine UK
- What Car UK

### 俄罗斯 / 中亚（5条，via RSS.app 转换）
- Drom.ru
- Kolesa.ru
- Kolesa.kz（哈萨克斯坦）
- Za Rulem（俄，За Рулём）
- Avtostat.ru

### 中东（6条，via RSS.app 转换）
- Drive Arabia（GCC）
- ArabWheels
- Gulf News Motors
- Arab Motor World
- Motory.sa（沙特）
- YallaMotor

### 东南亚（8条）
- paultan.org（马来西亚，SEA 最权威）
- WapCar（马）
- Headlightmag（泰）
- Bangkok Post Motoring
- sgCarMart News（新加坡）
- Torque SG
- CarBuyer SG
- Oto.com.vn（越南）

### 东亚（7条）
- Response.jp（日本）
- Car Watch（日）
- Best Car Web（日）
- The Korean Car Blog（英文，韩国市场）
- AutoTimes KR
- GoAuto HK
- HKGolden Motor

### 质量 / 监管（5条）
- SAMR 缺陷产品召回（中国）
- EU Safety Gate RAPEX XML（欧盟，每周）
- KBA 召回数据（德国，每周 CSV）
- NHTSA Recalls RSS（美国）
- Transport Canada Recalls（加拿大）

## Filter & Priority Logic

### 多语言关键词词典

```python
LI_AUTO_VARIANTS = [
    "理想汽车", "理想", "AITO", "Li Auto", "Lixiang",
    "Лисян", "Ли Сян",   # 俄语
    "리샹",               # 韩语
    "リシャン",           # 日语
    "ليكسيانغ",          # 阿拉伯语
]

CN_BRANDS = [
    "比亚迪", "BYD", "蔚来", "NIO", "小鹏", "XPENG",
    "吉利", "Geely", "华为问界", "AITO", "长城", "哈弗",
    "奇瑞", "Chery", "长安", "MG", "上汽", "SAIC",
    "零跑", "Leapmotor", "岚图", "Voyah", "极氪", "Zeekr",
    "深蓝", "仰望", "方程豹",
]

QUALITY_VARIANTS = [
    "召回", "recall", "Rückruf", "rappel", "отзыв",
    "استدعاء", "缺陷", "安全隐患", "故障", "投诉",
    "quality issue", "defect", "safety alert", "investigation",
]
```

### 优先级打分

| 优先级 | 条件 | 区块标题 |
|--------|------|---------|
| P0 🚨 | 理想汽车 + 质量/召回关键词 | 质量预警 & 召回 |
| P1 ⭐ | 理想汽车（任何话题） | 理想汽车动态 |
| P2 🇨🇳 | 其他中国品牌 | 中国品牌出海 |
| P3 🌍 | 全球品牌 / 行业趋势 | 国际品牌动态 |

## Feishu Card Format

每天推送 1-2 张飞书卡片（单张超过 20 条自动分拆）：

```
┌────────────────────────────────────────────────┐
│  🚗 汽车行业日报  2026-06-29  |  35 条新闻     │
└────────────────────────────────────────────────┘

🚨 质量预警 & 召回  (N条)
━━━━━━━━━━━━━━━━━━━━━━━
[Brand] [Title]
[100-word English summary]
🔗 [source link]  📍 [region]

⭐ 理想汽车动态  (N条)
🇨🇳 中国品牌出海  (N条)
🌍 国际品牌动态  (N条)
```

## GitHub Actions

```yaml
on:
  schedule:
    - cron: '0 1 * * *'   # 北京时间 09:00
  workflow_dispatch:

env:
  LLM_API_KEY: ${{ secrets.LLM_API_KEY }}
  LLM_BASE_URL: https://open.bigmodel.cn/api/paas/v4/
  LLM_MODEL: glm-4-flash
  FEISHU_BOT_WEBHOOK: ${{ secrets.FEISHU_BOT_WEBHOOK }}
```

## Cost Estimate

| 项目 | 月度成本 |
|------|---------|
| RSS 采集 | 免费 |
| GLM-4-flash（35条 × 700 tokens × 30天） | ≈ ¥10-15/月 |
| GitHub Actions（公开仓库） | 免费 |
| RSS.app（俄/中东 10个 feed 转换） | 免费套餐 |
| **合计** | **≈ ¥10-15/月** |

## Key Constraints

1. **外部内容隔离**：RSS 原文内容只放 user message，不注入 system prompt（防提示词注入）
2. **重试带熔断**：GLM 调用重试 3 次后熔断，单条失败不阻塞整批
3. **去重窗口**：`data/seen.json` 存 URL hash，3天滑动窗口防重复推送
4. **分批推送**：单张飞书卡片内容不超过 20 条，超出自动拆第二张
5. **监管平台降级**：中东/俄罗斯/中亚无官方 feed，质量问题依赖媒体报道覆盖
