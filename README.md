# 危险货物合规查询系统 (Dangerous Goods Compliance Query System)

基于联合国《关于危险货物运输的建议书》规章范本第23修订版（ST/SG/AC.10/1/Rev.23）的合规查询系统。

## 技术栈
- **后端**: FastAPI + SQLite + Uvicorn
- **前端**: 原生 HTML/CSS/JS（hash router，无框架依赖）
- **数据提取**: Python (pdfplumber)

## 数据来源
- **Vol.1**: 危险货物一览表（3.2章）— 2350 个 UN 编号（自动提取）
- **Vol.2**: 包装指南、罐柜指南等 — 待提取

## 快速启动

```bash
# 安装依赖
pip install -r backend/requirements.txt

# 初始化数据库（首次）
cd backend
python3 -c "from database import init_db, import_goods_csv, seed_regulations, seed_cn_names; init_db(); import_goods_csv(); seed_regulations(); seed_cn_names()"

# 启动服务
uvicorn main:app --host 0.0.0.0 --port 8199

# 访问
# http://localhost:8199/        → 前端页面
# http://localhost:8199/docs    → API 文档（Swagger）
```

## API 接口

| 接口 | 说明 |
|------|------|
| `GET /api/health` | 健康检查 + 数据统计 |
| `GET /api/goods/{un_number}` | 查询 UN 编号主表信息 |
| `GET /api/compliance/{un_number}` | 综合合规结果（基本信息 + 关联规则 + 检查单） |
| `GET /api/regulations/{code}` | 查询规则详情 |
| `GET /api/search?q=` | 搜索（UN/名称/规则编号） |
| `GET /api/browse?class=&page=` | 按类别浏览 |

## 数据提取

从 PDF 提取数据：

```bash
cd backend/scripts
python3 extract_vol1.py  # 提取 Vol.1 一览表 → CSV
```

手动数据放在 `data/manual_cn/` 目录下。

## 项目结构

```
├── backend/
│   ├── main.py              # FastAPI 应用入口
│   ├── database.py          # 数据库初始化 + 数据导入
│   ├── requirements.txt
│   ├── routes/              # API 路由（预留）
│   └── scripts/
│       └── extract_vol1.py  # Vol.1 数据提取脚本
├── frontend/
│   └── index.html           # 单页应用（hash router）
├── data/
│   ├── compliance.db         # SQLite 数据库（运行时生成）
│   ├── extracted_csv/        # 自动提取的 CSV 数据
│   └── manual_cn/           # 手动录入的中文数据
└── database/                # 预留数据库目录
```

## 当前数据统计

- UN 编号: 2350 条
- 已录入规则: 19 条（锂电池相关 SP/P/LP）
- 已录入中文名: 7 个

## 待办

- [ ] 提取 Vol.2 包装指南中文原文（P/LP/T/TP 系列）
- [ ] 补充更多品类的中文名称
- [ ] Docker 部署
- [ ] 管理后台
- [ ] 数据审核状态标记
