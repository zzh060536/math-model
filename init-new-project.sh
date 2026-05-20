#!/bin/bash
# Initialize a new math modeling project with the workflow manager
# Usage: bash init-new-project.sh <target-directory>
# Example: bash init-new-project.sh ~/Desktop/New-Modeling-Comp

set -e

TARGET="${1:?请指定目标目录，例如: bash init-new-project.sh ~/Desktop/新比赛}"

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "从 $SOURCE_DIR 复制工作流到 $TARGET ..."
mkdir -p "$TARGET"

# Copy workflow engine
cp -r "$SOURCE_DIR/workflow" "$TARGET/"
cp "$SOURCE_DIR/.gitignore" "$TARGET/"

# Create empty output directory
mkdir -p "$TARGET/output"

# Copy docs (optional)
cp -r "$SOURCE_DIR/docs" "$TARGET/" 2>/dev/null || true

# Check python-docx
python -c "import docx" 2>/dev/null && echo "python-docx: OK" || echo "请安装: pip install python-docx"

echo ""
echo "==============================================="
echo "  新项目初始化完成: $TARGET"
echo "==============================================="
echo ""
echo "下一步:"
echo "  1. 把题目 PDF 放到项目根目录，命名为 题目.pdf"
echo "  2. (可选) 把论文格式要求的 .docx 放到项目根目录"
echo "  3. 终端运行:"
echo "       cd $TARGET"
echo "       python workflow/manager.py"
echo ""
echo "  其他用法:"
echo "       python workflow/manager.py --stage 4    # 从阶段4开始"
echo "       python workflow/manager.py --reset      # 重置进度"
echo "       python workflow/manager.py --interactive # 每阶段手动确认"
