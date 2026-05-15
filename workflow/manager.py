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
    """Load and return JSON from path. Returns {} if file missing or malformed."""
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Warning: failed to decode JSON from {path}: {e}")
            return {}
    return {}


def save_json(path: Path, data: dict) -> None:
    """Save data as JSON to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
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


def call_claude(prompt: str, workdir: Path | None = None) -> str:
    """Invoke claude CLI with a prompt and return stdout."""
    cwd = str(workdir) if workdir else str(PROJECT_DIR)
    try:
        result = subprocess.run(
            ["claude", "--print", "--permission-mode", "bypassPermissions", prompt],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            cwd=cwd,
            encoding="utf-8",
            timeout=600,
        )
        if result.returncode != 0:
            print(f"[WARN] claude exited with code {result.returncode}")
            if result.stderr:
                print(f"[WARN] stderr: {result.stderr[:500]}")
        return result.stdout
    except subprocess.TimeoutExpired:
        print("[ERROR] claude 执行超时（600秒），请检查任务复杂度或网络连接")
        return ""
    except FileNotFoundError:
        print("[ERROR] 未找到 claude 命令，请确认 Claude Code 已安装并在 PATH 中")
        sys.exit(1)


def build_prompt(prompt_template: str, context: str, extra_vars: dict | None = None) -> str:
    """Build final prompt by substituting context and variables into template."""
    skills_instruction = (
        "【系统指令】你有权使用所有已安装的 Skills（技能）和 Tools（工具）。"
        "请根据任务需要主动调用相关 Skill，例如数学建模、数据处理、可视化等技能。"
        "任何可能相关的技能都应该被使用，不要只靠自己推理。\n\n"
    )
    prompt = skills_instruction + prompt_template
    prompt = prompt.replace("{{CONTEXT}}", context)
    prompt = prompt.replace("{{PROBLEM_FILE}}", str(PROJECT_DIR / "题目.pdf"))
    if extra_vars:
        for key, val in extra_vars.items():
            prompt = prompt.replace("{{" + key + "}}", str(val))
    return prompt


def save_output(output_path: str, content: str) -> None:
    """Save stage output to disk. Creates parent directories if needed.

    If output_path ends with /, it's a directory -- write to stage-output.md inside it.
    Otherwise write to the specified file path.
    """
    full_path = PROJECT_DIR / output_path
    if output_path.endswith("/") or output_path.endswith("\\"):
        # It's a directory -- create it and write stdout summary
        full_path.mkdir(parents=True, exist_ok=True)
        file_path = full_path / "stage-output.md"
    else:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        file_path = full_path
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  输出已保存: {file_path}")


def collect_context_summary(state: dict, config: dict, max_chars: int = 3000) -> str:
    """Build a summary of all prior stage outputs for context injection.

    Reads each prior stage's output file and truncates to max_chars total.
    """
    parts = []
    total = 0
    max_chars = config.get("max_context_summary_chars", 3000)
    for stage in config.get("stages", []):
        sid = str(stage.get("id", ""))
        if not sid:
            continue
        stage_info = state.get("stages", {}).get(sid, {})
        if stage_info.get("status") != "completed":
            continue
        output = stage_info.get("output", "")
        output_path = PROJECT_DIR / output
        if output_path.is_file() and output_path.exists():
            content = output_path.read_text(encoding="utf-8")
            header = f"\n\n=== 阶段 {sid}: {stage.get('name', '')} 输出 ===\n"
            chunk = header + content
            if total + len(chunk) > max_chars:
                remaining = max_chars - total
                if remaining > 200:
                    parts.append(chunk[:remaining] + "\n...[truncated]")
                break
            parts.append(chunk)
            total += len(chunk)
    return "".join(parts)


def execute_stage(stage: dict, state: dict, config: dict, extra_vars: dict | None = None) -> str:
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

    # Build prompt with extra vars
    prompt = build_prompt(prompt_template, context, extra_vars)

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

然后给出 2-4 个选项供用户选择。选项格式必须严格为：
[1] 继续下一阶段（当前结果可用）
[2] <具体修改建议1>
[3] <具体修改建议2>
[4] <具体修改建议3>（如果不需要就省略）

每个选项一行，以 [数字] 开头。在选项列表前，用 1-2 句话简要总结输出质量。"""
    options_output = call_claude(options_prompt)
    if not options_output.strip():
        options_output = (
            "输出质量评估：无法自动分析输出，请手动检查。\n"
            "[1] 继续下一阶段\n"
            "[2] 重新执行本阶段"
        )
    return options_output


def reset_stage_in_state(state: dict, stage_id: int) -> dict:
    """Reset a stage to allow re-execution."""
    state["stages"].pop(str(stage_id), None)
    state["current_stage"] = stage_id
    return state


def read_docx_templates() -> str:
    """Scan output/ and project root for .docx files and extract their text content.

    Returns combined formatting requirements, or empty string if no .docx found.
    """
    docx_files = []
    for scan_dir in [PROJECT_DIR / "output", PROJECT_DIR]:
        if scan_dir.exists():
            docx_files.extend(scan_dir.glob("*.docx"))
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
    for stage in config.get("stages", []):
        if stage.get("id") == stage_id:
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
        if choice in ("1", "n"):
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
    completed_count = sum(
        1 for s in state.get("stages", {}).values()
        if s.get("status") == "completed"
    )
    if completed_count > 0:
        print(f"  [恢复] 已完成 {completed_count}/7 阶段，当前: 阶段 {current_id}")
    else:
        print(f"  [新任务] 从头开始，共 7 阶段")
    print("=" * 60)

    stage = get_stage_by_id(config, current_id)
    if not stage:
        # Workflow complete
        print("\n  所有阶段已完成!")
        print(f"  最终输出: output/submission/")
        return

    # Warn if resuming an interrupted stage (will redo)
    stage_info = state.get("stages", {}).get(str(current_id), {})
    if stage_info.get("status") == "in_progress":
        print(f"\n  [注意] 阶段 {current_id} 上次被中断，将重新执行")

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
    options_text = execute_stage(stage, state, config, extra_vars)

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
            # Restart main for next stage
            main()
            return

        if choice == "redo":
            state = reset_stage_in_state(state, current_id)
            save_state(state)
            print(f"\n  重新执行阶段 {current_id}...")
            options_text = execute_stage(stage, state, config, extra_vars)
            continue

        if choice.startswith("custom:"):
            instruction = choice[7:]
            print(f"\n  根据反馈重新执行阶段 {current_id}...")
            prompt_path = PROMPTS_DIR / stage["prompt_file"]
            prompt_template = prompt_path.read_text(encoding="utf-8")
            context = collect_context_summary(state, config)
            base_prompt = build_prompt(prompt_template, context, extra_vars)
            revised_prompt = f"""用户对你上一轮的输出给出了以下修改意见：

{instruction}

请基于这些意见，重新完成阶段 {current_id}「{stage['name']}」的工作。
下面是你的原始任务提示：

{base_prompt}"""
            output = call_claude(revised_prompt)
            save_output(stage["output_file"], output)
            options_text = call_claude(
                f"你重新完成了阶段{current_id}的工作（已按用户要求：{instruction}）。"
                "请分析新输出并给出选项，格式同之前。"
            )
            continue


if __name__ == "__main__":
    main()
