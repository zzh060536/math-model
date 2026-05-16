#!/usr/bin/env python3
"""Math Modeling Workflow Manager — orchestrates Claude Code across 7 stages.

Usage:
  python workflow/manager.py              # Auto mode: run all stages
  python workflow/manager.py --stage N    # Start from stage N
  python workflow/manager.py --reset      # Reset all progress
"""

import subprocess
import json
import sys
import os
import signal
import argparse

# Fix Windows GBK encoding issues with Unicode output
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
STATE_PATH = PROJECT_DIR / "state.json"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Global flag for graceful Ctrl+C handling
_abort_requested = False


def _sigint_handler(signum, frame):
    global _abort_requested
    if _abort_requested:
        print("\n\n  强制退出...")
        sys.exit(1)
    _abort_requested = True
    print("\n\n  [Ctrl+C] 正在保存状态，请稍候...")
    print("  (再次按 Ctrl+C 强制退出)")


signal.signal(signal.SIGINT, _sigint_handler)


# ── JSON & State ──────────────────────────────────────────────

def load_json(path: Path) -> dict:
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Warning: failed to decode JSON from {path}: {e}")
            return {}
    return {}


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_config() -> dict:
    return load_json(CONFIG_PATH)


def load_state() -> dict:
    state = load_json(STATE_PATH)
    if not state:
        state = {
            "current_stage": 1,
            "started_at": datetime.now().isoformat(),
            "stages": {}
        }
    return state


def save_state(state: dict) -> None:
    state["updated_at"] = datetime.now().isoformat()
    save_json(STATE_PATH, state)


def mark_stage_complete(state: dict, stage_id: int, output_path: str) -> dict:
    state["stages"][str(stage_id)] = {
        "status": "completed",
        "output": output_path,
        "completed_at": datetime.now().isoformat()
    }
    return state


def mark_stage_in_progress(state: dict, stage_id: int) -> dict:
    state["current_stage"] = stage_id
    state["stages"][str(stage_id)] = {
        "status": "in_progress",
        "started_at": datetime.now().isoformat()
    }
    return state


def get_stage_by_id(config: dict, stage_id: int) -> dict | None:
    for stage in config.get("stages", []):
        if stage.get("id") == stage_id:
            return stage
    return None


def reset_state():
    """Reset all progress."""
    if STATE_PATH.exists():
        STATE_PATH.unlink()
    print("  进度已重置")


# ── Claude CLI ────────────────────────────────────────────────

SKILLS_SYSTEM_PROMPT = (
    "你有权使用所有已安装的 Skills（技能）和 Tools（工具）。"
    "这是强制要求——你必须主动调用 Skill 工具，绝不要仅靠自己的推理。"
    "由于运行在自动化模式（无用户交互），请遵守以下规则："
    "- 跳过任何需要用户输入/选择的技能（如 brainstorming），用自己推理替代"
    "- 数据可视化：调用 nature-figure 生成论文级图表"
    "- 论文撰写/检测：调用 chinese-thesis-workbench 规范中文论文"
    "- 代码求解：调用 superpowers:test-driven-development 保证质量"
    "- 完成后：调用 superpowers:verification-before-completion 验证"
)


def call_claude(prompt: str, workdir: Path | None = None, system_prompt: str = "") -> str:
    """Invoke claude CLI; returns stdout.

    If system_prompt is given, it's appended to the system prompt via
    --append-system-prompt, which is stronger than prompting.
    """
    cwd = str(workdir) if workdir else str(PROJECT_DIR)
    cmd = ["claude", "--print", "--permission-mode", "bypassPermissions"]
    if system_prompt:
        cmd.extend(["--append-system-prompt", system_prompt])
    cmd.append(prompt)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            cwd=cwd,
            encoding="utf-8",
            timeout=1800,
        )
        if result.returncode != 0:
            print(f"[WARN] claude exited with code {result.returncode}")
            if result.stderr:
                print(f"[WARN] stderr: {result.stderr[:500]}")
        return result.stdout
    except subprocess.TimeoutExpired:
        print("[ERROR] claude 执行超时（600秒）")
        return ""
    except FileNotFoundError:
        print("[ERROR] 未找到 claude 命令，请确认 Claude Code 已安装并在 PATH 中")
        sys.exit(1)


def build_prompt(prompt_template: str, context: str, extra_vars: dict | None = None) -> str:
    prompt = prompt_template
    prompt = prompt.replace("{{CONTEXT}}", context)
    prompt = prompt.replace("{{PROBLEM_FILE}}", str(PROJECT_DIR / "题目.pdf"))
    if extra_vars:
        for key, val in extra_vars.items():
            prompt = prompt.replace("{{" + key + "}}", str(val))
    return prompt


# ── Output & Context ──────────────────────────────────────────

def save_output(output_path: str, content: str) -> None:
    full_path = PROJECT_DIR / output_path
    if output_path.endswith("/") or output_path.endswith("\\"):
        full_path.mkdir(parents=True, exist_ok=True)
        file_path = full_path / "stage-output.md"
    else:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        file_path = full_path
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  输出已保存: {file_path}")


def collect_context_summary(state: dict, config: dict) -> str:
    parts = []
    total = 0
    max_chars = config.get("max_context_summary_chars", 3000)
    for stage_cfg in config.get("stages", []):
        sid = str(stage_cfg.get("id", ""))
        if not sid:
            continue
        stage_info = state.get("stages", {}).get(sid, {})
        if stage_info.get("status") != "completed":
            continue
        output = stage_info.get("output", "")
        output_path = PROJECT_DIR / output
        if output_path.is_file() and output_path.exists():
            content = output_path.read_text(encoding="utf-8")
            header = f"\n\n=== 阶段 {sid}: {stage_cfg.get('name', '')} 输出 ===\n"
            chunk = header + content
            if total + len(chunk) > max_chars:
                remaining = max_chars - total
                if remaining > 200:
                    parts.append(chunk[:remaining] + "\n...[truncated]")
                break
            parts.append(chunk)
            total += len(chunk)
    return "".join(parts)


def read_docx_templates() -> str:
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
        print("  [WARN] python-docx 未安装。运行: pip install python-docx")
        return ""
    parts = []
    for docx_path in docx_files:
        print(f"  读取格式模板: {docx_path.name}")
        doc = Document(str(docx_path))
        text = "\n".join(p.text for p in doc.paragraphs)
        parts.append(f"--- 格式要求来自 {docx_path.name} ---\n{text}")
    return "\n\n".join(parts)


# ── Stage Execution ───────────────────────────────────────────

def execute_stage(stage: dict, state: dict, config: dict, extra_vars: dict | None = None) -> str:
    """Execute one stage: build prompt → call Claude → save → return options text."""
    prompt_path = PROMPTS_DIR / stage["prompt_file"]
    if not prompt_path.exists():
        sys.exit(f"Prompt template not found: {prompt_path}")
    prompt_template = prompt_path.read_text(encoding="utf-8")

    context = collect_context_summary(state, config)
    if not context:
        context = "(这是第一个阶段，无前置上下文)"

    prompt = build_prompt(prompt_template, context, extra_vars)

    print(f"\n{'='*50}")
    print(f"  阶段 {stage['id']}/7: {stage['name']}")
    print(f"  {stage['description']}")
    print(f"{'='*50}")
    print(f"  正在执行... (调用 Claude Code，可能需要数分钟)\n")

    output = call_claude(prompt, system_prompt=SKILLS_SYSTEM_PROMPT)
    if _abort_requested:
        return ""

    if not output.strip():
        print("[ERROR] Claude 返回空结果")
        return (
            "输出质量评估：Claude 返回空结果。\n"
            "[1] 重新执行本阶段\n"
            "[2] 跳过，继续下一阶段"
        )

    save_output(stage["output_file"], output)

    # Generate quality assessment & options
    print(f"  正在分析输出质量...\n")
    options_prompt = f"""你刚刚完成了数学建模工作流的阶段 {stage['id']}「{stage['name']}」。
你的输出已保存到 {stage['output_file']}。

请分析输出质量（逻辑漏洞、遗漏、假设合理性），然后用 1-2 句话总结。
接着给出选项，格式必须严格为：
[1] 继续下一阶段（当前结果可用）
[2] <具体修改建议1>（如有必要）
[3] <具体修改建议2>（如有必要）

每个选项一行，以 [数字] 开头。如果没有需要修改的，只列 [1]。"""
    options_output = call_claude(options_prompt, system_prompt=SKILLS_SYSTEM_PROMPT)
    if _abort_requested:
        return ""

    if not options_output.strip():
        options_output = (
            "输出质量评估：无法自动分析。\n"
            "[1] 继续下一阶段\n"
            "[2] 重新执行本阶段"
        )
    return options_output


# ── Interactive Menu (only when user interrupts) ──────────────

def present_menu(options_text: str, stage_id: int) -> str:
    """Show options and wait for user choice."""
    print("\n" + "-" * 50)
    print(options_text)
    print("-" * 50)
    print(f"  [n/1] 继续下一阶段    [r] 重新执行阶段{stage_id}")
    print(f"  [c] 自定义修改要求    [q] 保存并退出")
    print()

    while True:
        try:
            choice = input("  请选择: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "quit"

        if choice in ("1", "n"):
            return "next"
        if choice in ("2", "3", "4"):
            lines = options_text.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith(f"[{choice}]"):
                    return "custom:" + line[4:].strip()
            return "redo"
        if choice == "r":
            return "redo"
        if choice == "c":
            try:
                custom = input("  请输入修改要求: ").strip()
            except (EOFError, KeyboardInterrupt):
                return "quit"
            if custom:
                return "custom:" + custom
            continue
        if choice == "q":
            return "quit"
        print("  无效选择，请重新输入")


# ── Main Loop ─────────────────────────────────────────────────

def run_workflow(interactive: bool = False, start_stage: int | None = None):
    global _abort_requested

    config = load_config()
    if not config.get("stages"):
        sys.exit("config.json 未找到或格式错误")

    state = load_state()

    # Override start stage if specified
    if start_stage is not None:
        state["current_stage"] = start_stage
        # Clear future stage records
        for sid in list(state.get("stages", {}).keys()):
            if int(sid) >= start_stage:
                del state["stages"][sid]

    current_id = state["current_stage"]

    print("=" * 60)
    print("  数学建模工作流管理器")
    completed_count = sum(
        1 for s in state.get("stages", {}).values()
        if s.get("status") == "completed"
    )
    total_stages = len(config["stages"])
    if completed_count > 0:
        print(f"  [恢复进度] 已完成 {completed_count}/{total_stages}，从阶段 {current_id} 继续")
    else:
        print(f"  [新任务] 共 {total_stages} 阶段，自动执行中...")
    print(f"  [提示] 按 Ctrl+C 可随时暂停并保存进度")
    print("=" * 60)

    while current_id <= total_stages:
        if _abort_requested:
            save_state(state)
            print(f"\n  状态已保存。下次运行从阶段 {current_id} 继续。")
            return

        stage = get_stage_by_id(config, current_id)
        if not stage:
            print("\n  所有阶段已完成!")
            print(f"  输出目录: output/submission/")
            return

        # Resume warning
        stage_info = state.get("stages", {}).get(str(current_id), {})
        if stage_info.get("status") == "in_progress":
            print(f"\n  [注意] 阶段 {current_id} 上次被中断，将重新执行")

        # Stage 6: scan docx templates
        extra_vars = {}
        if current_id == 6:
            print("\n  阶段 6 特殊处理: 搜索论文格式模板...")
            docx_content = read_docx_templates()
            extra_vars["DOCX_FORMAT"] = docx_content or "(无格式模板，使用标准竞赛论文格式)"

        # Mark in progress
        state = mark_stage_in_progress(state, current_id)
        save_state(state)

        # Execute
        options_text = execute_stage(stage, state, config, extra_vars)

        if _abort_requested:
            save_state(state)
            print(f"\n  状态已保存。下次运行从阶段 {current_id} 继续。")
            return

        # Decide: auto-continue or interactive menu
        if interactive:
            # ── Interactive mode ──
            while True:
                choice = present_menu(options_text, current_id)
                if choice == "quit":
                    save_state(state)
                    print(f"\n  状态已保存。下次运行从阶段 {current_id} 继续。")
                    return
                if choice == "next":
                    break
                if choice == "redo":
                    state["stages"].pop(str(current_id), None)
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
                    revised_prompt = (
                        f"用户修改意见：{instruction}\n\n"
                        f"请基于意见重新完成阶段 {current_id}「{stage['name']}」。\n"
                        f"原始任务：\n{base_prompt}"
                    )
                    output = call_claude(revised_prompt, system_prompt=SKILLS_SYSTEM_PROMPT)
                    save_output(stage["output_file"], output)
                    options_text = call_claude(
                        f"重新完成了阶段{current_id}（按用户意见：{instruction}）。"
                        "请分析新输出并给出选项，格式同之前。",
                        system_prompt=SKILLS_SYSTEM_PROMPT,
                    )
                    if not options_text.strip():
                        options_text = "[1] 继续下一阶段\n[2] 重新执行本阶段"
                    continue
        else:
            # ── Auto mode: show options, handle timeouts ──
            is_timeout = ("Claude 返回空结果" in options_text or
                          "无法自动分析" in options_text or
                          "claude 执行超时" in options_text)

            if is_timeout:
                print("\n" + "-" * 50)
                print(options_text)
                print("-" * 50)
                print(f"  [自动] Claude 超时，5秒后重试阶段 {current_id}...")
                print()
                import time
                time.sleep(5)  # Brief pause before retry
                options_text = execute_stage(stage, state, config, extra_vars)
                is_timeout = ("Claude 返回空结果" in options_text or
                              "无法自动分析" in options_text)

            if is_timeout:
                # Still failing — skip this stage
                print("\n" + "-" * 50)
                print(options_text)
                print("-" * 50)
                print(f"  [自动] 重试仍失败，跳过阶段 {current_id}，继续下一阶段")
                print()
            else:
                # Normal success or retry succeeded
                print("\n" + "-" * 50)
                print(options_text)
                print("-" * 50)
                print(f"  [自动] 已选择 [1] 继续下一阶段")
                print(f"  [提示] 如需干预，用 --interactive 运行，或按 Ctrl+C 暂停")
                print()

        # Mark complete, advance
        state = mark_stage_complete(state, current_id, stage["output_file"])
        current_id += 1
        state["current_stage"] = current_id
        save_state(state)

        if current_id <= total_stages:
            next_stage = get_stage_by_id(config, current_id)
            print(f"\n  → 进入阶段 {current_id}/7: {next_stage['name']}")

    # All done
    state["current_stage"] = total_stages + 1
    save_state(state)
    print("\n" + "=" * 60)
    print("  全部 7 个阶段已完成!")
    print(f"  最终输出: output/submission/")
    print("=" * 60)


# ── Entry Point ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="数学建模工作流管理器 — 自动驱动 Claude Code 完成建模竞赛"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="交互模式：每阶段完成后暂停，等待用户选择"
    )
    parser.add_argument(
        "--stage", "-s",
        type=int,
        metavar="N",
        help="从指定阶段开始（1-7）"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="重置所有进度，从头开始"
    )
    args = parser.parse_args()

    if args.reset:
        reset_state()

    start_stage = None
    if args.stage:
        if not 1 <= args.stage <= 7:
            sys.exit("阶段编号须在 1-7 之间")
        start_stage = args.stage

    run_workflow(interactive=args.interactive, start_stage=start_stage)


if __name__ == "__main__":
    main()
