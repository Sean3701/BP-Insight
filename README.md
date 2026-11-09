# 新版使用入口（2026-11-09）

日常请使用 `start_web.bat`，打开 http://127.0.0.1:8503/app/ 。新界面为「创建分析 / 报告库 / 模型设置」，保留全部旧资料。下方M04D说明仅供旧版兼容参考。

1. 在项目目录创建Python虚拟环境，运行 `python -m pip install -r requirements.txt`。
2. 双击 `start_web.bat`，或运行 `python launcher_web.py`。
3. 进入模型设置，编辑唯一默认的ChatGPT，填写OpenAI API Key，保存后测试连接。默认模型ID为 `gpt-5-mini`，可按账号权限修改。
4. 上传BP，确认自动建议名称，选择模型并生成报告。报告可下载PDF，右下角可持续追问。

密钥加密保存在本机数据库，主密钥位于 `data/secrets/master.key`；备份时保留整个data目录，切勿提交Git。此应用仅限本机loopback使用，没有登录/多用户权限。输入仅在明确发起分析、追问或连接测试时发送至配置的服务商。

新版需求与重建规格：`docs/项目需求与重建规格.md`。实施计划：`docs/superpowers/plans/2026-11-09-upload-analysis.md`。新版本支持真实API，旧M04D接口继续保留Mock流程。

开发验证：安装 `requirements-dev.txt` 后运行 `python -m pytest -q`。测试使用临时数据库，不触碰业务数据；外部网络由替身隔离。浏览器验收脚本 `tests/browser_smoke.cjs` 使用Playwright，启动 `tests/browser_fixture.py` 后运行；该测试服务仅限8504隔离验收，不用于日常研究。

OpenAI接口实现依据：[Text generation](https://developers.openai.com/api/docs/guides/text)、[Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)、[GPT-5 mini](https://developers.openai.com/api/docs/models/gpt-5-mini)。当前输出使用提示词JSON和本地结构校验，不要求其他服务商支持strict schema。

---

# VC Intelligence Platform

面向一级市场项目研究的 AI 投资分析平台。以 VC 业务作为首个应用，逐步连接 BP 文档、结构化项目档案、证据引用、分析工作流和报告。初期运行在 Windows 本地，后续扩展公司内部应用。

本仓库整理自 2026 年 11 月 6 日提供的项目代码，包含 M04D 模拟分析工作流。

## 当前能力

| 功能 | 当前状态 |
| --- | --- |
| 项目创建与列表 | 已实现，使用 SQLite 持久化 |
| BP 上传 | 支持 PDF、PPTX、DOCX、XLSX，单文件最大 25 MB |
| 文本与部分表格解析 | 已实现，保留页码、段落、幻灯片、工作表等来源位置 |
| 项目速览 | 7 类、29 个字段，支持按需展开证据 |
| 事实维护 | 人工录入、审核、驳回与不同值提示，作为可选校正入口 |
| 分析任务 | 后台执行 Mock 流程，保存任务状态、输入快照与报告 |
| 报告页面 | 查看已保存报告与证据，下载 JSON |
| 模型调用底座 | 提供 Mock 与 OpenAI 兼容接口适配器，演示智能体可调用 |
| BP 自动语义提取、AI 审核与正式投资评分 | 待实现，目前分析任务固定为 Mock |
| OCR、外部事实核验、知识库、偏好记忆、多模型对比 | 后续开发 |

Mock 表示模拟实现。当前分析流程使用固定规则和模板组织资料、已有事实与追问，自动提取替身返回空结果。已有事实和引用来自项目资料，评分字段留空。配置真实模型后，仍需要继续开发 BP 提取与分析模块，才能获得真实 AI 报告。

用户目标流程为上传 BP 后由 AI 自动整理和检查，人工按需核对。现有 Mock 任务可以直接对已解析的 BP 运行，人工录入与审核是可选步骤。

## 技术与目录

推荐 Python 3.11，原项目在 Windows / Python 3.11.9 环境使用。

- `backend/` 包含 FastAPI 接口、SQLAlchemy 模型、文档解析和后台任务。
- `frontend/` 包含 Streamlit 界面。
- `core/` 包含模型适配器、提取与证据接口、字段字典和工作流。
- `applications/vc_investment/` 预留业务应用扩展位置。
- `tests/` 包含本次上传项目中已有的 M02、M03、M04A 测试。
- `launcher.py` 负责 Windows 本地一键启动。
- `start_platform.bat` 是日常启动入口。
- `start_backend.bat` 与 `start_frontend.bat` 用于分别启动服务。
- `requirements.txt` 定义运行依赖。
- `.env.example` 是密钥留空的本地配置模板。
- `.gitignore` 定义环境、业务数据、缓存与备份等排除规则。

## 首次上传到已创建的 GitHub 仓库

推荐使用 GitHub Desktop，团队后续可以在同一流程中查看差异、提交、推送与合并。

1. 安装 GitHub Desktop 并登录有仓库权限的账号。
2. 打开 `File → Clone repository`，选择已创建的 `VC_Intelligence_Platform` 仓库。
3. 将 Local Path 设置为一个新的空目录，例如 `D:\VC_Intelligence_Platform_Team`，点击 Clone。
4. 解压整理后的代码包，将包内 `VC_Intelligence_Platform` 文件夹中的全部内容复制到刚刚克隆的目录。`backend`、`frontend`、`README.md` 应直接位于仓库根目录，避免再嵌套一层项目文件夹。
5. 用包内的 `README.md` 和 `.gitignore` 替换仓库创建时生成的同名文件。保留克隆时产生的 `.git` 目录。
6. 在 GitHub Desktop 的 Changes 中检查文件列表，确认环境配置、业务数据与备份均未列入提交。`.env.example` 应当在提交列表中，API Key 应为空。
7. 填写提交说明，例如“首次导入 M04D 项目代码和中文说明”，点击 `Commit to main`，再点击 `Push origin`。
8. 在 GitHub 网页确认仓库根目录显示源码与本 README，然后将仓库链接放进项目组文档。

网页上传也可用于首次导入。在当前仓库的 `Add file → Upload files` 中上传代码包解压后的内部文件与文件夹，确认预览保留正确目录结构。对已存在的 `README.md`、`.gitignore`，可以点击文件的编辑按钮，替换为本包内容后提交。网页上传时需自行确认选中的内容，不能依靠本地 `.gitignore` 自动过滤拖入的文件。

后续持续开发推荐使用 Desktop 克隆目录。ZIP 用于交付，仓库中保留展开后的文件。

## 新同事首次运行

克隆仓库后，每位同事在自己的电脑创建 Python 环境。下面以 `D:\VC_Intelligence_Platform_Team` 为例，命令在 CMD 中逐行执行。

```bat
cd /d D:\VC_Intelligence_Platform_Team
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
start_platform.bat
```

默认配置为 Mock，可以直接运行基础流程。若 `.env` 已存在，保留自己的配置。

| 地址或路径 | 用途 |
| --- | --- |
| `http://127.0.0.1:8501` | 日常使用网页 |
| `http://127.0.0.1:8000/health` | 后端健康检查 |
| `http://127.0.0.1:8000/docs` | 接口文档 |
| `data/database/vc_intelligence.db` | 本机数据库，运行时自动创建 |
| `data/uploads/` | 本机上传文件 |
| `data/logs/` | 启动与服务日志 |

日常双击当前仓库目录的 `start_platform.bat`。关闭时在启动窗口按 `Ctrl+C`。若原目录已有服务在运行，先停止旧窗口，以便新代码生效。

## 原开发者如何迁移到仓库目录

建议将克隆目录作为后续唯一的开发与运行目录，避免同时修改两套代码。

1. 停止旧目录 `D:\VC_Intelligence_Platform` 的前后端服务。
2. 按“新同事首次运行”在新仓库目录创建 `.venv` 并安装依赖。
3. 如要继续原来的项目记录，将旧目录的 `data` 整个文件夹复制到新仓库目录。服务完全停止后再复制，以保持数据库与上传文件一致。
4. 如要沿用原配置，将旧目录 `.env` 复制到新仓库目录。
5. 查看 GitHub Desktop 的 Changes，确认 `data` 与 `.env` 均被忽略。
6. 从新仓库目录启动并确认项目、文件和报告正常。此后所有代码修改和后续更新包都应用到这个目录。

虚拟环境请在新目录重新创建。原来的项目目录可作为迁移备份，确认新目录正常后再自行安排归档。

## 后续修改、覆盖与上传

### 自己修改代码

1. 打开 GitHub Desktop，确认当前仓库与分支。
2. 在开始改动前，保持工作区干净，点击 `Fetch origin`，有更新时点击 `Pull origin`。
3. 团队共同开发时，从最新 `main` 新建功能分支，例如 `feature/llm-extraction`。
4. 直接编辑本地仓库目录内的文件。
5. 运行平台验证相关功能，回到 Changes 检查差异。
6. 填写说明并 Commit，再 Push。首次推送新分支时按钮可能显示 `Publish branch`。
7. 创建 Pull Request，请另一位成员检查后合入 `main`。

`Commit` 将版本保存在本机，`Push` 将提交发送到 GitHub，`Pull` 将远端提交同步到本机。

### 收到别人或 AI 提供的更新文件

先提交或暂存自己尚未完成的改动，再同步远端，并在功能分支中应用更新。

- 只将明确说明需要修改的文件放到仓库对应相对路径。若更新内容为 `frontend/app.py`，目标就是仓库中的 `frontend/app.py`。
- 若更新包有安装器，将目标指向当前仓库目录。
- 在 Changes 中检查实际差异，尤其是同事也修改过的文件。整文件替换可能覆盖同事的新逻辑，应逐项合并后再测试提交。
- 后续接口变更需同时检查前后端和依赖。
- 合并请求中写明修改目的、验证方式与结果，便于团队审阅。

Git 会记录增删改，后续每次提交可以只包含相关文件。删除文件应在仓库内执行并提交删除记录。

### 同步同事的修改

工作区干净时执行 Fetch 和 Pull。若自己有未提交改动，先 Commit 或使用 Desktop 暂存功能。遇到冲突时，打开冲突文件，结合双方修改决定最终内容，确认后完成合并。

多人协作以功能分支和 Pull Request 为主。主分支保存可运行基线，验证通过的里程碑可打标签。

## 上传内容与排除内容

本次整理包保留当前运行源码、启动脚本、依赖和已有测试，新增本 README 与完善的忽略规则，并重新生成了密钥为空的配置模板。

| 类别 | 处理 |
| --- | --- |
| `applications/`、`backend/`、`core/`、`frontend/`、`tests/` | 上传源码 |
| `launcher.py`、启动脚本、`requirements.txt` | 上传 |
| `README.md`、`.gitignore`、`.env.example` | 上传 |
| `.env` | 在每台电脑本地保留 |
| `.venv/`、缓存目录 | 每位开发者自行创建 |
| `data/` 中的 BP、数据库和日志 | 在本机或有权限的业务资料系统管理 |
| `code_backups/`、旧升级 ZIP、备份版前端 | 排除 |
| 历史安装脚本、旧版 README、仅描述 M01 的架构说明 | 本次整理包已省略，当前说明汇总于本 README |

`.gitignore` 对尚未跟踪的文件生效。如果某个文件已经提交到 Git，后续添加忽略规则还需要另行取消跟踪。正式提交前查看 Changes 或 `git status`。

## 基础验收与开发测试

首次启动可依次检查项目创建、BP 上传与解析、速览与证据、事实维护、模拟分析、报告重开和重启后的持久化。

本次上传源码包含三个测试文件，对应五个已有测试用例。此前升级包中的新增测试文件未出现在本次上传的项目目录，因此仓库说明按实际收到的文件记录。

已有接口测试会在默认 `data` 目录写入测试项目、文件和记录。请在独立的临时克隆副本内执行，使用空白测试数据目录。开发测试依赖可另行安装。

```bat
.venv\Scripts\python.exe -m pip install pytest httpx reportlab
.venv\Scripts\python.exe -m pytest -q
```

后续团队开发应补齐 M04D 回归测试，并将测试数据库与业务数据库隔离。

## 后续开发目标

- 接入一个真实测试模型，完成 BP 自动提取、引用校验与 AI 检查。
- 固定评测材料、Prompt 和输出结构，对比不同模型的报告质量与成本。
- 生成适合投资负责人阅读的简洁诊断书，支持按需展开证据。
- 完善风险评分、尽调追问、OCR 与外部核验。
- 增加对话问答、项目记忆、后台偏好积累与专业智能体协作。
- 随公司业务推进权限管理、数据隔离、日志审计和服务器部署。

## GitHub 操作参考

- [下载 GitHub Desktop](https://desktop.github.com/)
- [克隆仓库](https://docs.github.com/en/desktop/adding-and-cloning-repositories/cloning-and-forking-repositories-from-github-desktop)
- [查看差异和提交](https://docs.github.com/en/desktop/making-changes-in-a-branch/committing-and-reviewing-changes-to-your-project-in-github-desktop)
- [同步分支](https://docs.github.com/en/desktop/working-with-your-remote-repository-on-github-or-github-enterprise/syncing-your-branch-in-github-desktop)
