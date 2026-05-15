# Math Modeling Workflow Automation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python workflow manager that orchestrates Claude Code through 7 stages of math modeling competition work, pausing at each stage for user decision.

**Architecture:** A single Python script (`manager.py`) drives a linear state machine. Each stage reads a prompt template, accumulates context from prior stages, calls `claude` CLI, saves output, then invokes Claude again to analyze its own output and generate multiple-choice options for the user. Stage 6 has special behavior to scan for .docx formatting templates.

**Tech Stack:** Python 3 (stdlib: subprocess, json, pathlib, argparse), `claude` CLI, python-docx (pip install)

---

## File Structure (post-implementation)

```
Math-model/
├── workflow/
│   ├── manager.py
│   ├── config.json
│   └── prompts/
│       ├── 01-problem-understanding.txt
│       ├── 02-method-selection.txt
│       ├── 03-model-building.txt
│       ├── 04-code-solving.txt
│       ├── 05-result-analysis.txt
│       ├── 06-paper-writing.txt
│       └── 07-packaging.txt
├── output/            (created at runtime)
├── state.json         (created at runtime)
├── .gitignore
└── docs/
```

---

### Task 1: Project scaffolding and .gitignore

**Files:**
- Create: `.gitignore`
- Create: `workflow/config.json`
- Create: `workflow/__init__.py` (empty)

- [ ] **Step 1: Write .gitignore**

```gitignore
output/
state.json
__pycache__/
*.pyc
.superpowers/
```

Create `c:/Users/31350/Desktop/Math-model/.gitignore` with the content above.

- [ ] **Step 2: Write config.json**

Create `c:/Users/31350/Desktop/Math-model/workflow/config.json`:

```json
{
  "stages": [
    {
      "id": 1,
      "name": "题目分析与理解",
      "prompt_file": "01-problem-understanding.txt",
      "output_file": "output/01-problem-understanding.md",
      "description": "提取关键信息，识别问题类型，拆分子问题"
    },
    {
      "id": 2,
      "name": "文献调研与方法选择",
      "prompt_file": "02-method-selection.txt",
      "output_file": "output/02-method-selection.md",
      "description": "搜索相关方法，比较候选模型，推荐方法组合"
    },
    {
      "id": 3,
      "name": "模型假设与建立",
      "prompt_file": "03-model-building.txt",
      "output_file": "output/03-model-building.md",
      "description": "提出假设，定义符号，推导公式，建立模型"
    },
    {
      "id": 4,
      "name": "编程求解",
      "prompt_file": "04-code-solving.txt",
      "output_file": "output/04-code/",
      "description": "编写求解代码，运行并保存结果"
    },
    {
      "id": 5,
      "name": "结果分析与验证",
      "prompt_file": "05-result-analysis.txt",
      "output_file": "output/05-analysis/",
      "description": "绘图，验证结果，灵敏度分析"
    },
    {
      "id": 6,
      "name": "论文撰写",
      "prompt_file": "06-paper-writing.txt",
      "output_file": "output/06-paper/",
      "description": "按竞赛格式生成 LaTeX 论文"
    },
    {
      "id": 7,
      "name": "最终打包提交",
      "prompt_file": "07-packaging.txt",
      "output_file": "output/submission/",
      "description": "整理文件结构，检查完整性，打包"
    }
  ],
  "claude_command": "claude",
  "problem_file": "题目.pdf",
  "project_dir": ".",
  "max_context_summary_chars": 3000
}
```

- [ ] **Step 3: Create empty __init__.py**

Create `c:/Users/31350/Desktop/Math-model/workflow/__init__.py` (empty file).

---

### Task 2: manager.py — core framework (imports, config loading, state management)

**Files:**
- Create: `workflow/manager.py`

- [ ] **Step 1: Write the skeleton with imports, config loading, and StateManager class**

Create `c:/Users/31350/Desktop/Math-model/workflow/manager.py`:

```python
#!/usr/bin/env python3
"""Math Modeling Workflow Manager — orchestrates Claude Code across 7 stages."""

import subprocess
import json
import sys
import os
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
STATE_PATH = PROJECT_DIR / "state.json"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_json(path: Path) -> dict:
    """Load and return JSON from path. Returns {} if file missing."""
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path: Path, data: dict) -> None:
    """Save data as JSON to path."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_config() -> dict:
    """Load workflow configuration."""
    return load_json(CONFIG_PATH)


def load_state() -> dict:
    """Load current workflow state, or return fresh state."""
    state = load_json(STATE_PATH)
    if not state:
        state = {
            "current_stage": 1,
            "started_at": datetime.now().isoformat(),
            "stages": {}
        }
    return state


def save_state(state: dict) -> None:
    """Persist workflow state to disk."""
    state["updated_at"] = datetime.now().isoformat()
    save_json(STATE_PATH, state)


def mark_stage_complete(state: dict, stage_id: int, output_path: str) -> dict:
    """Mark a stage as completed in state."""
    state["stages"][str(stage_id)] = {
        "status": "completed",
        "output": output_path,
        "completed_at": datetime.now().isoformat()
    }
    return state


def mark_stage_in_progress(state: dict, stage_id: int) -> dict:
    """Mark a stage as in progress."""
    state["current_stage"] = stage_id
    state["stages"][str(stage_id)] = {
        "status": "in_progress",
        "started_at": datetime.now().isoformat()
    }
    return state


def get_stage_context(state: dict, config: dict) -> list[str]:
    """Collect file paths of all prior stage outputs for context accumulation."""
    contexts = []
    for stage in config["stages"]:
        sid = str(stage["id"])
        if sid in state.get("stages", {}) and state["stages"][sid].get("status") == "completed":
            output = state["stages"][sid]["output"]
            ctx_path = PROJECT_DIR / output
            if ctx_path.is_dir():
                # For directories, list contents
                contexts.append(f"[Stage {sid} output directory: {output}]")
            elif ctx_path.exists():
                contexts.append(f"[Stage {sid} output: {output}]")
    return contexts
```

- [ ] **Step 2: Verify script starts without import errors**

Run: `cd "c:/Users/31350/Desktop/Math-model" && python workflow/manager.py`
Expected: No output, clean exit.

---

### Task 3: manager.py — Claude CLI invocation

**Files:**
- Modify: `workflow/manager.py` (append to existing)

- [ ] **Step 1: Add the call_claude function**

Append to `workflow/manager.py`:

```python
def call_claude(prompt: str, workdir: Path | None = None) -> str:
    """Invoke claude CLI with a prompt and return stdout.

    Uses the -p flag for non-interactive mode. The claude CLI
    automatically loads all installed skills, config, and memory.
    """
    cwd = str(workdir) if workdir else str(PROJECT_DIR)
    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        cwd=cwd,
        encoding="utf-8",
        timeout=600,  # 10 minutes per stage
    )
    if result.returncode != 0:
        print(f"[WARN] claude exited with code {result.returncode}")
        if result.stderr:
            print(f"[WARN] stderr: {result.stderr[:500]}")
    return result.stdout


def build_prompt(prompt_template: str, context: str, extra_vars: dict | None = None) -> str:
    """Build final prompt by substituting context and variables into template."""
    prompt = prompt_template
    prompt = prompt.replace("{{CONTEXT}}", context)
    prompt = prompt.replace("{{PROBLEM_FILE}}", str(PROJECT_DIR / "题目.pdf"))
    if extra_vars:
        for key, val in extra_vars.items():
            prompt = prompt.replace("{{" + key + "}}", str(val))
    return prompt
```

- [ ] **Step 2: Verify by importing in a dry-run check**

Run: `cd "c:/Users/31350/Desktop/Math-model" && python -c "from workflow.manager import call_claude, build_prompt; print('OK')"`
Expected: `OK`

---

### Task 4: manager.py — stage execution and output saving

**Files:**
- Modify: `workflow/manager.py` (append to existing)

- [ ] **Step 1: Add output saving and stage execution functions**

Append to `workflow/manager.py`:

```python
def save_output(output_path: str, content: str) -> None:
    """Save stage output to disk. Creates parent directories if needed."""
    full_path = PROJECT_DIR / output_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  输出已保存: {full_path}")


def collect_context_summary(state: dict, config: dict, max_chars: int = 3000) -> str:
    """Build a summary of all prior stage outputs for context injection.

    Reads each prior stage's output file and truncates to max_chars total.
    """
    parts = []
    total = 0
    max_chars = config.get("max_context_summary_chars", 3000)
    for stage in config["stages"]:
        sid = str(stage["id"])
        stage_info = state.get("stages", {}).get(sid, {})
        if stage_info.get("status") != "completed":
            continue
        output = stage_info.get("output", "")
        output_path = PROJECT_DIR / output
        if output_path.is_file() and output_path.exists():
            content = output_path.read_text(encoding="utf-8")
            header = f"\n\n=== 阶段 {sid}: {stage['name']} 输出 ===\n"
            chunk = header + content
            if total + len(chunk) > max_chars:
                remaining = max_chars - total
                if remaining > 200:
                    parts.append(chunk[:remaining] + "\n...[truncated]")
                break
            parts.append(chunk)
            total += len(chunk)
    return "".join(parts)


def execute_stage(stage: dict, state: dict, config: dict) -> str:
    """Execute a single stage and return the output content.

    1. Reads the prompt template
    2. Builds context from prior stages
    3. Calls Claude to do the work
    4. Saves output
    5. Calls Claude to analyze output and generate options
    6. Returns the analysis + options
    """
    # Load prompt template
    prompt_path = PROMPTS_DIR / stage["prompt_file"]
    if not prompt_path.exists():
        sys.exit(f"Prompt template not found: {prompt_path}")
    prompt_template = prompt_path.read_text(encoding="utf-8")

    # Build context
    context = collect_context_summary(state, config)
    if not context:
        context = "(这是第一个阶段，无前置上下文)"

    # Build prompt
    prompt = build_prompt(prompt_template, context)

    print(f"\n{'='*50}")
    print(f"  阶段 {stage['id']}/7: {stage['name']}")
    print(f"  {stage['description']}")
    print(f"{'='*50}")
    print(f"  正在执行... (调用 Claude Code)\n")

    # Call Claude
    output = call_claude(prompt)
    if not output.strip():
        print("[ERROR] Claude 返回空结果，请检查 claude CLI 是否可用")
        sys.exit(1)

    # Save output
    save_output(stage["output_file"], output)

    # Generate options for user
    print(f"  正在分析输出并生成选项...\n")
    options_prompt = f"""你刚刚完成了数学建模工作流的阶段 {stage['id']}「{stage['name']}」。
你的输出已保存到 {stage['output_file']}。

请分析你刚才的输出质量，特别注意：
1. 是否存在逻辑漏洞或遗漏
2. 关键假设是否合理
3. 是否需要补充内容

然后给出 3-4 个选项供用户选择。选项格式必须严格为：
[1] 继续下一阶段（当前结果可用）
[2] <具体修改建议1>
[3] <具体修改建议2>
[4] <具体修改建议3>（如果不需要3个修改建议就只列2个）

每个选项一行，以 [数字] 开头。在选项列表前，用 1-2 句话简要总结输出质量。"""
    options_output = call_claude(options_prompt)
    return options_output


def reset_stage_in_state(state: dict, stage_id: int) -> dict:
    """Reset a stage to allow re-execution."""
    state["stages"].pop(str(stage_id), None)
    state["current_stage"] = stage_id
    return state
```

- [ ] **Step 2: Verify**

Run: `cd "c:/Users/31350/Desktop/Math-model" && python -c "from workflow.manager import execute_stage, save_output, collect_context_summary; print('OK')"`
Expected: `OK`

---

### Task 5: manager.py — main interactive loop

**Files:**
- Modify: `workflow/manager.py` (append to existing)

- [ ] **Step 1: Add the main() function**

Append to `workflow/manager.py`:

```python
def read_docx_templates() -> str:
    """Scan output/ for .docx files and extract their text content.

    Returns combined formatting requirements, or empty string if no .docx found.
    """
    output_dir = PROJECT_DIR / "output"
    docx_files = list(output_dir.glob("*.docx"))
    if not docx_files:
        print("  未找到 .docx 格式模板文件，使用默认格式")
        return ""

    try:
        from docx import Document
    except ImportError:
        print("  [WARN] python-docx 未安装，无法读取 Word 模板。运行: pip install python-docx")
        return ""

    parts = []
    for docx_path in docx_files:
        print(f"  读取格式模板: {docx_path.name}")
        doc = Document(str(docx_path))
        text = "\n".join(p.text for p in doc.paragraphs)
        parts.append(f"--- 格式要求来自 {docx_path.name} ---\n{text}")
    return "\n\n".join(parts)


def get_stage_by_id(config: dict, stage_id: int) -> dict | None:
    """Get stage config by id."""
    for stage in config["stages"]:
        if stage["id"] == stage_id:
            return stage
    return None


def present_options(options_text: str) -> str:
    """Display options and get user choice. Returns 'next' or 'redo' or 'custom:...'."""
    print("\n" + "-" * 50)
    print(options_text)
    print("-" * 50)
    print("  [n] 继续下一阶段")
    print("  [r] 重新执行本阶段")
    print("  [c] 输入自定义修改要求")
    print("  [q] 保存并退出")
    print()

    while True:
        choice = input("  请选择: ").strip().lower()
        if choice in ("1", "n", ""):
            return "next"
        if choice in ("2", "3", "4"):
            # Map number options to custom instruction
            lines = options_text.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith(f"[{choice}]"):
                    return "custom:" + line[4:].strip()
            return "redo"
        if choice == "r":
            return "redo"
        if choice == "c":
            custom = input("  请输入修改要求: ").strip()
            if custom:
                return "custom:" + custom
            continue
        if choice == "q":
            return "quit"
        print("  无效选择，请重新输入")


def main():
    config = load_config()
    if not config.get("stages"):
        sys.exit("config.json 未找到或格式错误")

    state = load_state()
    current_id = state["current_stage"]

    print("=" * 60)
    print("  数学建模工作流管理器")
    print(f"  当前进度: 阶段 {current_id}/7")
    print("=" * 60)

    stage = get_stage_by_id(config, current_id)
    if not stage:
        # Workflow complete
        print("\n  所有阶段已完成!")
        print(f"  最终输出: output/submission/")
        return

    # Check for .docx templates before stage 6
    extra_vars = {}
    if current_id == 6:
        print("\n  阶段 6 特殊处理: 搜索论文格式模板...")
        docx_content = read_docx_templates()
        if docx_content:
            extra_vars["DOCX_FORMAT"] = docx_content
        else:
            extra_vars["DOCX_FORMAT"] = "(无格式模板，请使用标准竞赛论文格式)"

    # Mark stage in progress
    state = mark_stage_in_progress(state, current_id)
    save_state(state)

    # Execute stage
    options_text = execute_stage(stage, state, config)

    # Handle user choice
    while True:
        choice = present_options(options_text)

        if choice == "quit":
            save_state(state)
            print(f"\n  状态已保存。下次运行继续阶段 {state['current_stage']}。")
            return

        if choice == "next":
            state = mark_stage_complete(state, current_id, stage["output_file"])
            next_id = current_id + 1
            if next_id > len(config["stages"]):
                state["current_stage"] = 8  # All done
                save_state(state)
                print("\n  全部 7 个阶段已完成! 输出在 output/submission/")
                return
            state["current_stage"] = next_id
            save_state(state)
            print(f"\n  进入阶段 {next_id}: {get_stage_by_id(config, next_id)['name']}")
            break

        if choice == "redo":
            state = reset_stage_in_state(state, current_id)
            save_state(state)
            print(f"\n  重新执行阶段 {current_id}...")
            options_text = execute_stage(stage, state, config)
            continue

        if choice.startswith("custom:"):
            instruction = choice[7:]
            print(f"\n  根据反馈重新执行阶段 {current_id}...")
            # Build a revised prompt incorporating the user's instruction
            prompt_path = PROMPTS_DIR / stage["prompt_file"]
            prompt_template = prompt_path.read_text(encoding="utf-8")
            context = collect_context_summary(state, config)
            base_prompt = build_prompt(prompt_template, context)
            revised_prompt = f"""用户对你上一轮的输出给出了以下修改意见：

{instruction}

请基于这些意见，重新完成阶段 {current_id}「{stage['name']}」的工作。
下面是你的原始任务提示：

{base_prompt}"""
            output = call_claude(revised_prompt)
            save_output(stage["output_file"], output)
            # Re-analyze for options
            options_text = call_claude(
                f"你重新完成了阶段{current_id}的工作（已按用户要求：{instruction}）。"
                "请分析新输出并给出选项，格式同之前。"
            )
            continue

    # Loop to next stage
    main()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify syntax**

Run: `cd "c:/Users/31350/Desktop/Math-model" && python -c "import py_compile; py_compile.compile('workflow/manager.py', doraise=True); print('No syntax errors')"`
Expected: `No syntax errors`

---

### Task 6: Write the 7 prompt templates

**Files:**
- Create: `workflow/prompts/01-problem-understanding.txt`
- Create: `workflow/prompts/02-method-selection.txt`
- Create: `workflow/prompts/03-model-building.txt`
- Create: `workflow/prompts/04-code-solving.txt`
- Create: `workflow/prompts/05-result-analysis.txt`
- Create: `workflow/prompts/06-paper-writing.txt`
- Create: `workflow/prompts/07-packaging.txt`

- [ ] **Step 1: Write prompt 01 — Problem Understanding**

Create `c:/Users/31350/Desktop/Math-model/workflow/prompts/01-problem-understanding.txt`:

```
你是一名数学建模竞赛专家。你现在处于工作流的第1阶段：题目分析与理解。

请阅读题目文件：{{PROBLEM_FILE}}

任务：
1. 提取题目中的关键信息（背景、数据、约束条件）
2. 识别问题的类型（优化、预测、评价、分类等）
3. 将复杂问题拆解为 2-4 个子问题
4. 明确每个子问题的已知条件和求解目标
5. 列出题目中的关键数据和参数

输出格式：使用 Markdown，包含以下章节：
- 问题背景
- 问题类型识别
- 子问题拆解
- 已知条件与求解目标
- 关键数据与参数

前置阶段输出（用于参考，本阶段是第一阶段，以下为空）：
{{CONTEXT}}
```

- [ ] **Step 2: Write prompt 02 — Method Selection**

Create `c:/Users/31350/Desktop/Math-model/workflow/prompts/02-method-selection.txt`:

```
你是一名数学建模竞赛专家。你现在处于工作流的第2阶段：文献调研与方法选择。

前置阶段输出：
{{CONTEXT}}

任务：
1. 针对每个子问题，列出 2-3 种可用的数学方法或算法
2. 对每种方法进行简要比较（优缺点、适用性、复杂度）
3. 给出推荐的方法组合和理由
4. 列出所需的数据来源或参数估计方法
5. 如果需要，使用 WebSearch 搜索相关方法的适用场景

输出格式：使用 Markdown，包含：
- 子问题1：候选方法与比较
- 子问题2：候选方法与比较
- ...
- 推荐方法组合
- 数据需求清单
```

- [ ] **Step 3: Write prompt 03 — Model Building**

Create `c:/Users/31350/Desktop/Math-model/workflow/prompts/03-model-building.txt`:

```
你是一名数学建模竞赛专家。你现在处于工作流的第3阶段：模型假设与建立。

前置阶段输出：
{{CONTEXT}}

任务：
1. 针对每个子问题，提出合理的基本假设（3-6条）
2. 定义所有变量和参数的符号（建立符号表）
3. 推导数学模型（写出完整的数学公式）
4. 明确目标函数、约束条件
5. 说明模型的创新点或特色

重要要求：
- 每个假设需要说明合理性
- 变量符号使用 LaTeX 格式（如 $x_i$, $\lambda$）
- 推导过程要完整、可验证
- 考虑模型的通用性和可扩展性

输出格式：使用 Markdown，包含：
- 基本假设
- 符号说明表
- 模型推导
- 目标函数与约束条件
- 模型特点分析
```

- [ ] **Step 4: Write prompt 04 — Code Solving**

Create `c:/Users/31350/Desktop/Math-model/workflow/prompts/04-code-solving.txt`:

```
你是一名数学建模竞赛专家。你现在处于工作流的第4阶段：编程求解。

前置阶段输出：
{{CONTEXT}}

任务：
1. 根据第3阶段建立的数学模型，编写 Python 求解代码
2. 代码需要结构化、有注释、可直接运行
3. 将代码文件保存到 output/04-code/ 目录
4. 运行代码并保存数值结果到 output/04-code/results.json
5. 如果模型需要数据输入，生成合理的测试数据或用题目给出的数据

重要要求：
- 代码必须有清晰的函数和注释
- 输出结果包括关键变量的数值
- 如果涉及优化，输出最优解和最优值
- 如果涉及预测，输出预测值和置信区间
- 代码运行后不要有错误

输出：先输出一段说明（代码结构和运行方式），然后输出完整的 Python 代码（用 ```python 包裹）。
```

- [ ] **Step 5: Write prompt 05 — Result Analysis**

Create `c:/Users/31350/Desktop/Math-model/workflow/prompts/05-result-analysis.txt`:

```
你是一名数学建模竞赛专家。你现在处于工作流的第5阶段：结果分析与验证。

前置阶段输出：
{{CONTEXT}}

任务：
1. 读取第4阶段的数值结果
2. 绘制必要的图表（折线图、柱状图、热力图等）保存到 output/05-analysis/figures/
3. 验证模型结果的合理性（单位检查、量级检查、边界情况）
4. 进行灵敏度分析：改变关键参数，观察结果变化
5. 讨论模型的优缺点和改进方向

重要要求：
- 图表使用 matplotlib/seaborn，中文标签需处理字体
- 每个图表需要有标题和轴标签
- 灵敏度分析至少改变2个关键参数
- 结果分析要实事求是，不要夸大

输出格式：使用 Markdown，包含：
- 数值结果汇总
- 图表展示与分析
- 结果合理性验证
- 灵敏度分析
- 模型优缺点讨论
```

- [ ] **Step 6: Write prompt 06 — Paper Writing**

Create `c:/Users/31350/Desktop/Math-model/workflow/prompts/06-paper-writing.txt`:

```
你是一名数学建模竞赛专家。你现在处于工作流的第6阶段：论文撰写。

前置阶段输出：
{{CONTEXT}}

论文格式要求：
{{DOCX_FORMAT}}

任务：
1. 根据前5个阶段的全部输出，撰写完整的竞赛论文
2. 论文使用 LaTeX 格式，保存到 output/06-paper/main.tex
3. 如果提供了 Word 格式模板，严格遵循其格式要求
4. 论文结构应包含：
   - 摘要（300字以内，概述问题、方法、结果）
   - 问题重述
   - 模型假设与符号说明
   - 模型建立与求解（按子问题分节）
   - 结果分析与验证
   - 模型评价与改进
   - 参考文献
   - 附录（关键代码）

重要要求：
- 使用中文撰写（ctex 文档类或 xeCJK）
- 数学公式使用 LaTeX 语法
- 图表引用使用 \includegraphics
- 引用前阶段生成的图表文件
- 参考文献格式规范
- 论文总字数控制在合理范围内

输出：生成完整的 main.tex 文件内容（用 ```latex 包裹）。
```

- [ ] **Step 7: Write prompt 07 — Packaging**

Create `c:/Users/31350/Desktop/Math-model/workflow/prompts/07-packaging.txt`:

```
你是一名数学建模竞赛专家。你现在处于工作流的第7阶段：最终打包提交。

前置阶段输出：
{{CONTEXT}}

任务：
1. 检查所有输出文件的完整性
2. 整理文件结构到 output/submission/ 目录
3. 复制最终论文 PDF（如有）到 submission/
4. 复制关键代码到 submission/code/
5. 复制图表到 submission/figures/
6. 生成 README 说明文件
7. 生成提交文件清单

输出：列出 submission/ 目录中的所有文件，并给出提交建议。
```

---

### Task 7: Integration test — verify workflow starts

**Files:**
- Verify: `workflow/manager.py` runs cleanly (dry-run check)

- [ ] **Step 1: Create initial state and verify startup**

Run:
```bash
cd "c:/Users/31350/Desktop/Math-model" && python -c "
from workflow.manager import *
config = load_config()
state = load_state()
print(f'Stages: {len(config[\"stages\"])}')
print(f'Current stage: {state[\"current_stage\"]}')
print(f'Manager OK')
"
```
Expected:
```
Stages: 7
Current stage: 1
Manager OK
```

- [ ] **Step 2: Verify prompt templates exist**

Run:
```bash
cd "c:/Users/31350/Desktop/Math-model" && python -c "
from workflow.manager import PROMPTS_DIR, load_config
config = load_config()
for s in config['stages']:
    p = PROMPTS_DIR / s['prompt_file']
    exists = 'OK' if p.exists() else 'MISSING'
    print(f'  Stage {s[\"id\"]}: {s[\"prompt_file\"]} [{exists}]')
"
```
Expected: All 7 show `[OK]`

- [ ] **Step 3: Verify python-docx availability**

Run:
```bash
pip install python-docx 2>&1 | tail -1
```

---

### Task 8: Final commit

- [ ] **Step 1: Verify file structure**

Run:
```bash
cd "c:/Users/31350/Desktop/Math-model" && find . -not -path './.git/*' -not -path './.superpowers/*' -not -name '*.pdf' | sort
```
Expected: Shows all workflow files in the correct structure.

- [ ] **Step 2: Initialize git and commit**

```bash
cd "c:/Users/31350/Desktop/Math-model"
git init
git add .gitignore workflow/ docs/
git commit -m "feat: add math modeling workflow manager with 7-stage pipeline"
```
