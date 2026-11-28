# 非遗手工艺传承工作台

手工艺传承人、学徒和技艺保护专员共同管理技艺图谱、传承档案与作品认证，确保每一项非遗技艺有完整的师徒传承与作品记录。

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/WorkbenchView.vue|tsx  全部模块共享工作台
│   ├── src/data/modules.ts              18个业务模块配置
│   ├── src/api/              统一请求封装
│   └── vite.config.ts        dev server 配置（open: false）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/resource.py  通用查询/导出/登记/动作接口
│   ├── app/services/<key>.py    每个模块独立领域逻辑
│   ├── app/services/base.py     共享服务骨架
│   └── app/store.py          内存数据仓库与示例数据
├── .gitignore
└── docker-compose.yml
```

## 启动

### 后端

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run.sh
```

健康检查：`curl http://127.0.0.1:8000/api/health`

### 前端

```bash
cd frontend
npm ci
npm run dev
```

前端默认监听 `http://127.0.0.1:5173/`，dev server 不会自动打开浏览器，
需要自己访问。`/api` 由 vite 代理到后端 `http://127.0.0.1:8000`。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 技艺分类 | `craft_category` | 技艺门类 | 门类名称、所属级别、申报批次 |
| 传承人档案 | `artisan` | 传承人 | 姓名、技艺方向、传承谱系 |
| 学徒培养 | `apprentice` | 学徒 | 学徒姓名、拜师日期、学习阶段 |
| 技艺图谱 | `skill_card` | 技艺卡片 | 技艺名称、工艺流程、核心原料 |
| 原材料管理 | `raw_material` | 原料批次 | 原料名称、产地来源、采购日期 |
| 工具器械 | `tooling` | 工具 | 工具名称、制作材质、维护周期 |
| 传习所管理 | `workshop` | 传习所 | 场所名称、所在地区、容纳人数 |
| 培训方案 | `training_plan` | 培训计划 | 课程名称、授课师傅、培训周期 |
| 作品创作 | `creation_work` | 作品 | 作品名称、所用技艺、创作周期 |
| 作品认证 | `authentication` | 认证 | 认证类型、评审专家、认证日期 |
| 展览策划 | `exhibition` | 展览活动 | 展览主题、展出地点、展期起止 |
| 资助经费 | `grant_fund` | 经费申请 | 申请项目、资助来源、获批金额 |
| 田野调查 | `field_survey` | 调查记录 | 调查地点、调查日期、访谈对象 |
| 数字化采集 | `digitization` | 数字资源 | 资源类型、采集设备、分辨率规格 |
| 出版成果 | `publication` | 出版物 | 出版物名称、编著者、出版社 |
| 知识产权 | `ip_right` | 权属登记 | 权利类型、权利人、登记日期 |
| 传承评估 | `evaluation` | 评估报告 | 评估对象、评估周期、评分结果 |
| 濒危抢救 | `emer_rescue` | 抢救项目 | 濒危等级、抢救方案、实施团队 |

## 申报批次迁移与调查归档

旧「申报批次」是自由录入的名称，同名门类跨年度无法区分。迁移后：

- 门类新增 `年度`、`申报批次标识`（`年度-批次名称-序号`，如 `2023-秋季申报-01`）
  和 `调查归档批号`（如 `DA-2023-001`）。
- 部署窗口内旧 `申报批次`、`登记编号` 继续保留，旧编号仍可查。
- 年度可确认的存量批次自动迁移并发号；**年度无法确认的批次标记为「待补年度」，
  不发放可写入的新编号**，需档案员通过「补正年度」提交带依据的年份后才发号。
- 同名的不同年度批次按（门类名称, 年度, 批次）分别成组，不因标题相同而合并。
- 田野调查归档优先使用 `调查归档批号`，归档时按同一批次重取原组证据；
  未核对的历史批次只能按旧门类与旧批次号只读查阅。
- 已归档材料始终可以按旧门类和原编号取回原件；停用新版批次界面不影响旧号查阅。

相关接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/batch-category/migrate` | 执行申报批次迁移（幂等） |
| GET | `/api/batch-category/batches` | 批次迁移概况 |
| POST | `/api/batch-category/{id}/correct-year` | 提交带依据的年份补正 |
| GET | `/api/batch-category/lookup` | 按门类/批次/年度/原编号/归档批号查批次 |
| POST | `/api/field_survey/{id}/archive` | 用归档批号（或旧编号）实际归档 |
| GET | `/api/field_survey/{id}/locators` | 核对归档批号与原编号能否分别定位 |
| GET | `/api/field_survey/archive-lookup` | 按旧门类/旧批次号/原编号取归档原件 |
| GET/POST | `/api/batch-ui` | 新版批次界面开关（停用不影响旧号查阅） |

## 约定

- 全部模块共享`frontend/src/views/WorkbenchView.vue|tsx`和一套资源路由。
- 每个模块仍保留独立`backend/app/services/<模块>.py`；纯前端保留
  `frontend/src/domain/<模块>.ts`，用于承载真实业务差异并维持36题位容量。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。

领域：应用开发
子方向：web前端
