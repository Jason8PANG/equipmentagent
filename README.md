# 🔧 设备维修智能助手 (Equipment Maintenance Assistant)

基于 Flask + MySQL 的设备维修故障查询与记录管理系统，集成千问 AI 智能分析，支持 Web 端 + 手机端访问。

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| **故障智能查询** | 输入故障现象，自动匹配历史维修记录，输出诊断报告（故障频次、解决方案排行、涉及设备） |
| **AI 智能总结** | 可选调用千问大模型（qwen3.6-plus），对查询结果进行自然语言总结分析 |
| **维修记录录入** | 技术员通过 Web 表单提交维修记录，支持拍照上传 |
| **联动下拉框** | 设备名称→设备编号联动、故障类别→故障明细联动、技术员列表 |
| **移动端适配** | 查询页 + 录入页均已适配手机屏幕（480px/640px 断点） |
| **Docker 部署** | 支持一键 Docker Compose 部署，适用于 CentOS 等 Linux 环境 |

---

## 🏗️ 技术架构

```
┌──────────────────────────────────────────────┐
│                  浏览器 / 手机                 │
│         http://equipmentagentapp:5000         │
└──────────────────┬───────────────────────────┘
                   │
┌──────────────────▼───────────────────────────┐
│           Docker: equipmentagentapp           │
│  ┌──────────────────────────────────────┐    │
│  │     Waitress WSGI (port 5000)        │    │
│  │  ┌────────────────────────────────┐  │    │
│  │  │        Flask Web App           │  │    │
│  │  │   /         查询对话界面        │  │    │
│  │  │   /add      维修记录录入        │  │    │
│  │  │   /api/*    REST API           │  │    │
│  │  └────────────────────────────────┘  │    │
│  └──────────────────────────────────────┘    │
└──────────────────┬───────────────────────────┘
                   │
     ┌─────────────┼─────────────┐
     ▼                           ▼
┌─────────────┐          ┌──────────────┐
│  MySQL DB   │          │ 千问 AI API  │
│ 10.0.6.86   │          │  (Token Plan) │
│ :33306      │          │  qwen3.6-plus │
└─────────────┘          └──────────────┘
```

### 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Flask 3.x |
| 数据库 | MySQL (pymysql) |
| AI 模型 | 千问 qwen3.6-plus (阿里云 MaaS Token Plan) |
| 生产服务器 | Waitress WSGI |
| 容器化 | Docker + Docker Compose |
| 前端 | 原生 HTML/CSS/JS，响应式布局 |

### 查询引擎原理

- **中文分词**：2~4 字滑动窗口切词
- **多字段 LIKE 评分**：故障现象、故障明细、解决方案、设备名称等字段加权匹配
- **Counter 统计**：按故障类别、解决方案、设备等维度聚合统计
- **AI 增强**：将统计报告发送给千问大模型，生成自然语言总结（**仅用户点击触发，不消耗默认查询的 Token**）

---

## 📦 快速开始

### 前置条件

- Python 3.11+ (本地开发)
- Docker & Docker Compose (生产部署)
- MySQL 数据库（需预先创建 `erp_data` 库）
- 千问 Token Plan API Key（AI 总结功能可选）

### 本地开发

```bash
cd maintenance-web

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（复制模板后填入真实值）
cp .env.example .env

# 启动开发服务器
python app.py
# 访问 http://localhost:5000
```

### Docker 部署

```bash
cd maintenance-web

# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入真实 API Key 和数据库密码

# 2. 创建 Docker 网络（首次）
docker network create public-net

# 3. 构建并启动
docker-compose up -d

# 4. 查看日志
docker logs -f equipmentagentapp
```

部署后访问地址：
- **Docker 网络内**：`http://equipmentagentapp:5000`
- **宿主机**：`http://localhost:5000`

### 环境变量说明

| 变量 | 必填 | 说明 | 默认值 |
|------|:--:|------|--------|
| `QWEN_API_KEY` | 否 | 千问 Token Plan API Key | - |
| `QWEN_BASE_URL` | 否 | 千问 API 地址 | `https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` |
| `QWEN_MODEL` | 否 | 千问模型名称 | `qwen3.6-plus` |
| `MYSQL_HOST` | 是 | MySQL 服务器地址 | `10.0.6.86` |
| `MYSQL_PORT` | 是 | MySQL 端口 | `33306` |
| `MYSQL_USER` | 是 | MySQL 用户名 | `powerbi` |
| `MYSQL_PASSWORD` | 是 | MySQL 密码 | - |
| `MYSQL_DATABASE` | 是 | 数据库名 | `erp_data` |
| `MYSQL_CHARSET` | 否 | 数据库字符集 | `utf8mb4` |

---

## 📁 项目结构

```
maintenance-web/
├── app.py                  # Flask 主应用（路由 + API）
├── config.py               # 环境变量配置（自动加载 .env）
├── query_engine.py         # MySQL 查询引擎 + AI 总结
├── requirements.txt        # Python 依赖
├── Dockerfile              # Docker 镜像定义
├── docker-compose.yml      # Docker Compose 编排
├── .dockerignore           # Docker 构建排除
├── .env.example            # 环境变量模板
├── .gitignore              # Git 排除规则
├── README.md               # 本文件
├── static/
│   ├── css/style.css       # 样式表
│   ├── js/app.js           # 前端逻辑
│   └── uploads/            # 上传文件存储
└── templates/
    ├── index.html          # 查询对话界面
    └── add.html            # 维修记录录入界面
```

---

## 🔌 API 接口

| 路由 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 查询对话界面 |
| `/add` | GET | 维修记录录入界面 |
| `/api/chat` | POST | 故障查询（`{"query": "..."}`） |
| `/api/ai-summary` | POST | AI 总结（`{"query": "...", "report": {...}}`) |
| `/api/equipment-list` | GET | 设备名称列表 |
| `/api/equip-codes` | GET | 设备名称→编号查询 |
| `/api/fault-details` | GET | 故障类别→明细查询 |
| `/api/technicians` | GET | 技术员列表 |
| `/api/submit` | POST | 提交维修记录（含文件上传） |

---

## 📝 数据库说明

MySQL 数据库部署在 `10.0.6.86:33306`，包含以下核心表：

- **repair_records**：维修记录主表（故障现象、故障类别、故障明细、解决方案、设备信息、技术员、时间等）
- **repair_attachments**：维修记录附件表（照片、文件等）

迁移脚本：
- `migrate_master_data.py`：导入设备主数据
- `migrate_to_mysql.py`：导入历史维修记录

---

## 📄 License

Internal use — NAI Group

---

## 👤 维护者

yan.shen@nai-group.com
