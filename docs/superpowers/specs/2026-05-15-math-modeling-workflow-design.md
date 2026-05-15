# Math Modeling Workflow Automation — Design Spec

## Overview

A Python-based workflow manager that orchestrates Claude Code to solve math modeling competition problems end-to-end. The program drives 7 stages (problem understanding → final submission), calling `claude` CLI for each stage, accumulating context, and pausing at each stage boundary for user decision via multiple-choice options.

## Architecture

```
题目.pdf
    │
    ▼
workflow/manager.py ──→ state.json
    │
    ├── prompts/ (7 prompt templates)
    │
    ▼
claude CLI (subprocess) ──→ Skills + Memory + Tools all active
    │
    ▼
output/ (organized per stage)
    │
    └── user confirms → next stage
```

## File Structure

```
Math-model/
├── workflow/
│   ├── manager.py              # Entry point, state machine, CLI
│   ├── config.json             # Stage definitions, paths
│   └── prompts/
│       ├── 01-problem-understanding.txt
│       ├── 02-method-selection.txt
│       ├── 03-model-building.txt
│       ├── 04-code-solving.txt
│       ├── 05-result-analysis.txt
│       ├── 06-paper-writing.txt
│       └── 07-packaging.txt
├── output/
│   ├── 01-problem-understanding.md
│   ├── 02-method-selection.md
│   ├── 03-model-building.md
│   ├── 04-code/
│   ├── 05-analysis/
│   ├── 06-paper/
│   └── submission/
├── state.json
└── .gitignore
```

## State Machine

7 stages, linear progression. At each stage boundary: Claude analyzes its output, generates 2-4 suggested next actions, user picks one. Actions can be: confirm-next, redo-with-changes, or custom instruction. Most options are generated dynamically by Claude based on the actual output quality.

```json
{
  "current_stage": 3,
  "stages": {
    "1": {"status": "completed", "output": "output/01-...md"},
    "2": {"status": "completed", "output": "output/02-...md"},
    "3": {"status": "in_progress"}
  }
}
```

## Stage Summary

| # | Stage | Input | Output | Key Decision |
|---|-------|-------|--------|--------------|
| 1 | 题目分析 | 题目 PDF | problem-understanding.md | 理解是否准确 |
| 2 | 方法选择 | Stage 1 output | method-selection.md | 方法方向是否正确 |
| 3 | 模型建立 | Stages 1-2 | model-building.md | 假设是否合理 |
| 4 | 编程求解 | Stages 1-3 | code/ + results.json | 代码能否运行 |
| 5 | 结果分析 | Stage 4 results | analysis.md + figures/ | 图表结论是否满意 |
| 6 | 论文撰写 | Stages 1-5 + .docx template | LaTeX paper + PDF | 论文质量 |
| 7 | 打包提交 | All outputs | submission/ | 完整性检查 |

## Stage 6 Special Behavior

Before generating the paper, scan `output/` for `.docx` files. Extract formatting requirements using python-docx. Inject the requirements into the prompt: "Use the following formatting guidelines: {docx_content}".

## Interaction Design

After each stage completes:
- Claude analyzes output quality, identifies issues
- Presents 2-4 suggested options (continue / fix specific issues / custom)
- User picks one by number or writes custom instruction
- Options are generated dynamically — not hardcoded

## Key Details

- **Claude invocation**: `claude -p "<prompt>"` with accumulated context from prior stages
- **Checkpoint recovery**: state.json persists every stage transition; interrupted runs resume
- **Prompt accumulation**: Each stage prompt includes summaries of all prior stage outputs
- **Word doc handling**: python-docx library to extract text from .docx formatting templates

## Tech Stack

- Python 3 (assumed available)
- `claude` CLI (already installed)
- python-docx (for reading Word format templates)
- Standard library: subprocess, json, pathlib, sys
