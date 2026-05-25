# 数学建模智能体

基于 AI 的数学建模竞赛全流程自动化工​具。拖拽上传题目，一键完成从问题分析到论文撰写的 7 个阶段，支持 Claude Code 和 Codex CLI 双引擎。

## 功能概览

- **拖拽上传** — 支持 PDF / TXT 题目文件，自动识别问题类型
- **7 阶段自动化建模** — 题目分析 → 方法选择 → 模型建立 → 编程求解 → 结果分析 → 论文撰写 → 打包提交
- **双 AI 引擎** — Claude Code（Skills 生态）和 Codex CLI（OpenAI GPT-5.3），网页一键切换
- **多项目隔离** — 每个题目独立文件夹，互不干扰，支持项目历史管理
- **实时进度** — 侧边栏状态追踪，进度条可视化
- **论文修改面板** — 按章节提交修改意见，记录追踪
- **深色主题 Web 界面** — 响应式设计，Markdown 渲染 + 代码高亮 + 图片预览

## 快速开始

### 环境要求

- Python 3.10+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) 或 [Codex CLI](https://github.com/openai/codex)
- Flask、markdown、Pillow

### 安装

```bash
git clone https://github.com/zzh060536/math-model.git
cd math-model
pip install flask markdown pillow zhipuai python-docx
```

### 启动

```bash
# Windows 双击
start.bat

# 或命令行
python workflow/web.py
```

浏览器自动打开 `http://localhost:5000`。

## 使用流程

1. **新建项目** — 点击「新建项目」，为题目命名（如 `2024国赛A题`）
2. **上传题目** — 拖拽 PDF 或 TXT 文件到上传区
3. **选择引擎** — 顶部切换 Claude Code / Codex CLI
4. **开始建模** — 点击橙色按钮，7 个阶段自动执行
5. **查看结果** — 点击侧边栏各阶段查看输出，图表和代码均可预览
6. **论文修改** — 在反馈面板按章节提交修改意见

### 自定义要求

在「自定义要求」文本框中可指定特殊需求：

```
约束处理：确保满足车辆容量约束和时间窗约束。
使用遗传算法求解路径优化问题。
重点关注模型的鲁棒性分析。
```

## 项目结构

```
├── workflow/
│   ├── web.py              # Flask Web 服务
│   ├── manager.py           # 7 阶段流程编排
│   ├── config.json          # 阶段配置 + Agent 配置
│   ├── prompts/             # 各阶段提示词模板
│   ├── templates/           # 前端 HTML
│   └── static/              # CSS / JS
├── projects/                # 项目数据（gitignore）
│   ├── 2024国赛A题/
│   │   ├── 题目.pdf
│   │   ├── state.json
│   │   └── output/
│   └── ...
├── start.bat                # Windows 一键启动
└── init-new-project.sh      # 新建项目脚本
```

## 阶段说明

| 阶段 | 名称 | 输出 |
|------|------|------|
| 1 | 题目分析与理解 | `output/01-problem-understanding.md` |
| 2 | 文献调研与方法选择 | `output/02-method-selection.md` |
| 3 | 模型假设与建立 | `output/03-model-building.md` |
| 4 | 编程求解 | `output/04-code/` |
| 5 | 结果分析与验证 | `output/05-analysis/` |
| 6 | 论文撰写 | `output/06-paper/` |
| 7 | 最终打包提交 | `output/submission/` |

## Agent 切换

编辑 `workflow/config.json` 或在网页顶部切换：

```json
{
  "agent": {
    "provider": "claude",
    "claude": {
      "command": "claude",
      "args": ["--print", "--permission-mode", "bypassPermissions"]
    },
    "codex": {
      "command": "codex",
      "args": ["exec", "--approval-mode", "full-auto"]
    }
  }
}
```

## 许可

MIT
