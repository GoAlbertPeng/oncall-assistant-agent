# OnCall 助手 Agent

AI 驱动的告警分析平台，帮助 OnCall 人员快速定位问题根因并生成处理工单。

## 功能特性

- **智能告警分析**：输入告警信息，自动收集日志和指标上下文，通过大模型分析根因
- **多数据源支持**：支持 Elasticsearch/ELK、Grafana Loki、Prometheus 数据源
- **工单管理**：一键生成工单，支持状态流转管理
- **现代化界面**：基于 React + Ant Design 的响应式 Web 界面

## 技术栈

- **后端**：Python 3.11 + FastAPI + SQLAlchemy
- **前端**：React 18 + TypeScript + Ant Design 5
- **数据库**：MySQL 8.0
- **LLM**：支持 OpenAI API 及兼容接口

## 快速开始

### 使用 Docker Compose（推荐）

1. **克隆项目**
```bash
git clone <repository-url>
cd oncall-assistant-agent
```

2. **配置环境变量**
```bash
# 复制环境变量模板
cp backend/.env.example .env

# 编辑 .env 文件，配置你的 LLM API Key
# OPENAI_API_KEY=your-api-key
```

3. **启动服务**
```bash
docker-compose up -d
```

4. **访问应用**
- 前端界面：http://localhost
- API 文档：http://localhost:8000/docs
- 默认账号：admin@oncall.example.com / admin123

### 本地开发

#### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 配置数据库和 LLM

# 启动开发服务器
uvicorn app.main:app --reload --port 8000
```

#### 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 项目结构

```
oncall-assistant-agent/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── connectors/     # 数据源连接器
│   │   ├── models/         # 数据库模型
│   │   ├── schemas/        # Pydantic 模型
│   │   ├── services/       # 业务逻辑
│   │   ├── config.py       # 配置管理
│   │   ├── database.py     # 数据库连接
│   │   └── main.py         # 应用入口
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── components/     # 通用组件
│   │   ├── pages/          # 页面组件
│   │   ├── services/       # API 调用
│   │   └── stores/         # 状态管理
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml      # Docker 编排
├── init.sql               # 数据库初始化
└── README.md
```

## API 接口

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 认证 | POST | `/api/auth/login` | 用户登录 |
| 认证 | GET | `/api/auth/me` | 获取当前用户 |
| 数据源 | GET | `/api/datasources` | 列表查询 |
| 数据源 | POST | `/api/datasources` | 新增数据源 |
| 数据源 | PUT | `/api/datasources/{id}` | 编辑数据源 |
| 数据源 | DELETE | `/api/datasources/{id}` | 删除数据源 |
| 数据源 | POST | `/api/datasources/{id}/test` | 测试连通性 |
| 分析 | POST | `/api/analysis` | 提交告警分析 |
| 分析 | GET | `/api/analysis/{id}` | 查询分析结果 |
| 分析 | GET | `/api/analysis` | 历史会话列表 |
| 工单 | POST | `/api/tickets` | 创建工单 |
| 工单 | GET | `/api/tickets` | 工单列表 |
| 工单 | GET | `/api/tickets/{no}` | 工单详情 |
| 工单 | PATCH | `/api/tickets/{no}` | 更新工单状态 |

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | MySQL 数据库连接 URL | - |
| `JWT_SECRET_KEY` | JWT 签名密钥 | - |
| `JWT_EXPIRE_HOURS` | JWT 过期时间（小时） | 24 |
| `LLM_PROVIDER` | LLM 提供商 | openai |
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `OPENAI_MODEL` | OpenAI 模型名称 | gpt-4 |
| `OPENAI_BASE_URL` | OpenAI API 地址 | https://api.openai.com/v1 |

### 数据源配置

#### Elasticsearch / ELK

- 类型：`elk`
- 默认端口：9200
- 配置项：`index` - 日志索引模式，如 `logs-*`

#### Grafana Loki

- 类型：`loki`
- 默认端口：3100
- 配置项：`labels` - 日志标签过滤

#### Prometheus

- 类型：`prometheus`
- 默认端口：9090

## 使用指南

### 1. 配置数据源

在开始分析前，需要先配置数据源：

1. 进入「数据源管理」页面
2. 点击「添加数据源」
3. 选择数据源类型并填写连接信息
4. 点击「测试」验证连通性
5. 保存配置

### 2. 告警分析

1. 进入「告警分析」页面
2. 在输入框中粘贴或输入告警信息
3. 点击「开始分析」
4. 系统将自动：
   - 收集相关日志和指标
   - 调用大模型分析根因
   - 输出分析结果和处理建议

### 3. 创建工单

1. 分析完成后，点击「生成工单」
2. 编辑工单标题、根因和等级
3. 提交工单
4. 在「工单管理」页面跟踪处理进度

## 常见问题

### Q: 分析结果不准确？

- 确保数据源配置正确且有相关数据
- 检查告警时间范围内是否有日志和指标
- 尝试提供更详细的告警信息

### Q: 连接数据源失败？

- 检查网络连通性
- 确认认证信息正确
- 检查防火墙配置

### Q: LLM 调用失败？

- 检查 API Key 是否正确
- 确认网络可以访问 API 地址
- 查看后端日志获取详细错误信息

## 许可证

MIT License
