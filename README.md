# 主力基金持仓分析

抓取**规模 + 业绩**双指标达标的「主力基金」列表，解析它们的季报重仓股，把结果按**行业版块**聚合展示，并支持按**股价区间、行业**筛选。

> 数据源：东方财富（eastmoney.com）+ 腾讯（qt.gtimg.cn，备用）

---

## 功能特性

| 模块 | 说明 |
| --- | --- |
| 主力基金池 | 规模 ≥ 10 亿 且 近 1 年收益 ≥ 20% 的股票型 / 混合型 / 指数型基金 |
| 重仓股解析 | 季报前 10 大重仓（每年 4 次自动 + 手动触发） |
| 行业聚合 | 按「所属一级行业」分组展示，平均涨跌幅、持仓市值、持仓基金数 |
| 多维筛选 | 规模 / 1年收益 / 股价区间 / 行业 / 排序方式 |
| 详情页 | 单只股票 + 反向重仓基金；单只基金 + 重仓股明细 |
| 拖拽排序 | 行业卡片可拖拽调整顺序（前端 localStorage） |
| 双模式更新 | 定时任务（5 分钟一次行情 / 每日 17 点基金）+ 手动触发 |

---

## 项目结构

```
share/
├── backend/                # FastAPI + SQLite
│   ├── app/
│   │   ├── api/            # 路由：funds / holdings / stocks / sectors / jobs / filters
│   │   ├── models/         # SQLAlchemy：Fund / FundHolding / Stock / StockQuote / Sector / JobLog
│   │   ├── services/       # 业务：fund_service / stock_service / aggregation / filter_service
│   │   ├── scrapers/       # 抓取器：eastmoney_funds / fund_holdings / stock_quotes / stock_detail / sectors
│   │   ├── scheduler/      # APScheduler 定时任务
│   │   ├── main.py         # FastAPI 入口
│   │   ├── database.py     # SQLAlchemy + WAL 模式
│   │   └── config.py       # pydantic-settings 配置
│   ├── data/               # SQLite 数据文件
│   ├── requirements.txt
│   └── fix_encoding.py     # 一次性脚本：修复被错误编码的中文名
└── frontend/               # Vite + React 18 + TypeScript + Tailwind
    ├── src/
    │   ├── pages/          # DashboardPage / FundListPage / FundDetailPage / StockDetailPage / SettingsPage
    │   ├── components/     # FilterBar / SectorBoard / SectorCard / StockChip / AppShell / RangeSlider
    │   ├── api/            # axios 客户端 + 各资源 fetcher
    │   ├── store/          # zustand：filterStore
    │   ├── hooks/          # useDebounce
    │   └── types/          # API 类型定义
    └── package.json
```

---

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # 按需修改端口 / DB 路径 / 抓取配置
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

健康检查：<http://127.0.0.1:8000/api/health>

API 文档（Swagger）：<http://127.0.0.1:8000/docs>

### 2. 前端

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

### 3. 首次数据抓取

第一次启动数据库是空的，需要手动触发 3 步：

| 顺序 | 动作 | 接口 | 预计耗时 |
| --- | --- | --- | --- |
| 1 | 抓取基金列表 + 重仓股 | `POST /api/jobs/funds/refresh` | 5–10 分钟 |
| 2 | 抓取股票详情（行业 / 名称） | `POST /api/jobs/stock-details/refresh` | 1–2 分钟 |
| 3 | 抓取行情（持仓股） | `POST /api/jobs/quotes/refresh?only_holdings=true` | 30 秒 |

也可以打开前端「设置」页一键点击这 3 个按钮。

---

## 核心 API

| Method | URL | 说明 |
| --- | --- | --- |
| `GET` | `/api/holdings/by-sector?min_scale=10&min_ret_1y=20&industry_name=电子设备&price_min=10&price_max=200&sort_by=fund_count&page=1&page_size=200` | **核心**：按行业分组的持仓股票 |
| `GET` | `/api/funds?min_scale=10&min_ret_1y=20&fund_type=gp&page=1&page_size=50` | 主力基金列表 |
| `GET` | `/api/funds/{code}` | 基金详情 |
| `GET` | `/api/funds/{code}/holdings` | 基金重仓股 |
| `GET` | `/api/stocks/{code}` | 股票基本信息 |
| `GET` | `/api/stocks/{code}/quote` | 股票最新行情 |
| `GET` | `/api/stocks/{code}/funds` | 反向：哪些主力基金重仓了这只股票 |
| `GET` | `/api/sectors/by-industry` | 行业列表（用于筛选下拉） |
| `GET` | `/api/filters/defaults` | 默认筛选值（min_scale / min_ret_1y） |
| `GET` | `/api/jobs` | 最近 50 条任务日志 |
| `GET` | `/api/jobs/scheduled` | 已注册的定时任务 |
| `POST` | `/api/jobs/funds/refresh` | 手动触发基金抓取 |
| `POST` | `/api/jobs/quotes/refresh?only_holdings=true` | 手动触发行情抓取 |
| `POST` | `/api/jobs/sectors/refresh` | 手动触发行业抓取（push2 限流时使用） |
| `POST` | `/api/jobs/stock-details/refresh` | 手动触发股票详情抓取（emweb 端点，限流时仍可用） |

### 返回结构示例（by-sector）

```json
{
  "total": 211,
  "page": 1,
  "page_size": 200,
  "report_date": "2026-03",
  "sectors": [
    {
      "industry_name": "电子设备",
      "stock_count": 118,
      "avg_change_pct": -2.56,
      "total_market_value": 4316000000.0,
      "stocks": [
        {
          "code": "688012",
          "name": "中微公司",
          "industry_name": "电子设备",
          "price": 363.10,
          "change_pct": -6.90,
          "market_cap": 3477.93,
          "fund_count": 65,
          "total_market_value": 356370000.0,
          "total_ratio": 2538.58
        }
      ]
    }
  ]
}
```

---

## 数据源与抓取策略

| 数据 | 主源 | 备用源 | 备注 |
| --- | --- | --- | --- |
| 基金排行 | `fund.eastmoney.com/data/rankhandler.aspx` | — | 翻页拉取所有股票型 / 混合型 / 指数型 |
| 基金持仓 | `fundf10.eastmoney.com/FundArchivesDatas.aspx` | — | 季报前 10 大 |
| 股票行情（批量） | `push2.eastmoney.com/api/qt/clist/get` | `qt.gtimg.cn`（逐只） | **push2 经常被 IP 限流**，抓取器自动回退到腾讯 |
| 股票行业 | `emweb.eastmoney.com/PC_HSF10/...` | — | 单股接口，push2 限流时仍可用 |

> **重要**：东方财富的 `push2.*` 端点对单 IP 有严格限流（每个 IP 一天数百次后开始 empty reply），生产环境请配置代理（`CRAWL_PROXY`）或改用其他数据源。

---

## 排错速查

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `/api/holdings/by-sector` 返回 500 | `aggregation.py` 内聚合 SQL 出错 | 看 uvicorn 日志，定位到具体行；常因数据空 → 已加防御 |
| 股票名显示 6 位数字 | 行情抓取尚未回填 stock.name | 等抓取完；或在「设置」点「抓取行业+成分股」 |
| 行业全显示「未分类」 | 行业抓取失败 | 改用 `/api/jobs/stock-details/refresh`（走 emweb 端点） |
| 行情 / 行业抓取一直失败 | push2 端点被限流 | 等几小时，或配置代理 |
| 中文名乱码（如 `ã°é»`） | 抓取时把 UTF-8 字节当 Latin-1 写库 | 跑 `python fix_encoding.py` 一次性修复 |
| 浮点数很大 | `total_market_value` 是「元」为单位 | 前端展示时除以 1e8 / 1e4 |

---

## 设计说明

- **主力基金筛选条件**（可在前端「设置」调整）：
  - 规模 ≥ 10 亿
  - 近 1 年收益 ≥ 20%
  - 类型：股票型 / 混合型 / 指数型
- **聚合策略**：SQL 取最新一期持仓 → JOIN stock + 最新行情 → 内存里按行业分组、排序、分页
- **分页粒度**：按「行业级」分页，每页返回若干行业卡片，每卡最多 6 只股票 + 「+N 只」省略号
- **数据更新策略**：
  - 行情：每 5 分钟（交易时间内）抓一次
  - 基金：每天 17:00 抓一次
  - 行业 / 股票详情：每天 18:00 抓一次
  - 用户可在「设置」随时手动触发

---

## 已知限制 / TODO

- [ ] push2 限流时行业抓取只能靠 emweb 单股接口，并发 10 → 211 只股票约 30s
- [ ] 持仓股「shares（持股数）」当前为 0（仅 market_value 准确）— 是季报 HTML 表格列结构差异导致，待修复
- [ ] 概念板块（subject）尚未抓取
- [ ] 没做用户系统（单人本地用，不需要）

---

## License

仅供个人研究使用。请遵守数据源网站的 robots.txt 与使用条款。
