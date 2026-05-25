"""数学建模工作流 — 多项目 Web 界面"""
import json
import os
import sys
import signal
import shutil
import threading
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, jsonify, request, send_file
import markdown

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_DIR / "workflow" / "config.json"
PROJECTS_DIR = PROJECT_DIR / "projects"

app = Flask(__name__, template_folder=str(PROJECT_DIR / "workflow" / "templates"),
            static_folder=str(PROJECT_DIR / "workflow" / "static"))

_workflow_process = None
_current_project = None
_process_lock = threading.Lock()


# ── Helpers ──

def _get_project(name: str) -> Path:
    safe = name.replace("\\", "/").strip("/")
    if not safe or ".." in safe:
        raise ValueError("Invalid project name")
    return PROJECTS_DIR / safe


def _project_state_file(name: str) -> Path:
    return _get_project(name) / "state.json"


def _project_feedback_file(name: str) -> Path:
    return _get_project(name) / "output" / "revision-feedback.json"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state(project: str):
    p = _project_state_file(project)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_feedback(project: str):
    p = _project_feedback_file(project)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_feedback(project: str, feedback_list):
    p = _project_feedback_file(project)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(feedback_list, f, ensure_ascii=False, indent=2)


def get_stage_content(project: str, stage: dict):
    output_path = _get_project(project) / stage["output_file"]
    if not output_path.exists():
        return {"type": "empty", "content": "此阶段尚未生成内容"}

    if output_path.is_file():
        text = output_path.read_text(encoding="utf-8", errors="replace")
        html = markdown.markdown(text, extensions=["tables", "fenced_code"])
        return {"type": "markdown", "content": html, "raw": text}

    result = {"type": "directory", "files": [], "figures": []}
    for f in sorted(output_path.rglob("*")):
        if f.is_file():
            rel = str(f.relative_to(output_path)).replace("\\", "/")
            low = f.suffix.lower()
            if low in (".png", ".jpg", ".jpeg", ".svg"):
                result["figures"].append(rel)
            elif low in (".md", ".txt", ".tex", ".py", ".json", ".pdf"):
                result["files"].append({
                    "name": rel,
                    "suffix": f.suffix,
                    "size": f.stat().st_size
                })
    return result


def problem_exists(project: str):
    p = _get_project(project)
    return (p / "题目.pdf").exists() or (p / "题目.txt").exists()


def _run_workflow_bg(project: str):
    global _workflow_process
    try:
        proj_dir = _get_project(project)
        log_dir = proj_dir / "output"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = open(str(log_dir / "workflow.log"), "w", encoding="utf-8")
        env = os.environ.copy()
        env["MATHMODEL_PROJECT"] = project
        env["MATHMODEL_PROJECT_DIR"] = str(proj_dir)
        _workflow_process = subprocess.Popen(
            [sys.executable, str(PROJECT_DIR / "workflow" / "manager.py"),
             "--project", project, "--project-dir", str(proj_dir)],
            cwd=str(PROJECT_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
        )
        _workflow_process.wait()
        log_file.close()
    except Exception:
        pass
    finally:
        with _process_lock:
            _workflow_process = None


# ── Routes ──

@app.route("/")
def index():
    config = load_config()
    # List projects for the frontend
    projects = _list_projects()
    return render_template("index.html", stages=config["stages"],
                           projects=projects)


def _list_projects():
    result = []
    if PROJECTS_DIR.exists():
        for d in sorted(PROJECTS_DIR.iterdir(), reverse=True):
            if d.is_dir():
                state = load_state(d.name)
                completed = sum(1 for s in state.get("stages", {}).values()
                                if s.get("status") == "completed")
                has_problem = (d / "题目.pdf").exists() or (d / "题目.txt").exists()
                result.append({
                    "name": d.name,
                    "has_problem": has_problem,
                    "completed_stages": completed,
                    "total_stages": 7,
                    "created_at": state.get("started_at", ""),
                    "running": False,  # simplified — only one workflow at a time
                })
    return result


@app.route("/api/projects", methods=["GET"])
def api_list_projects():
    return jsonify(_list_projects())


@app.route("/api/projects", methods=["POST"])
def api_create_project():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "项目名称不能为空"}), 400
    if "/" in name or "\\" in name or ".." in name:
        return jsonify({"ok": False, "error": "项目名称不能包含特殊字符"}), 400
    proj_dir = PROJECTS_DIR / name
    if proj_dir.exists():
        return jsonify({"ok": False, "error": "项目已存在"}), 409
    proj_dir.mkdir(parents=True, exist_ok=True)
    return jsonify({"ok": True, "name": name})


@app.route("/api/projects/<name>", methods=["DELETE"])
def api_delete_project(name):
    try:
        proj_dir = _get_project(name)
    except ValueError:
        return jsonify({"ok": False, "error": "无效的项目名称"}), 400
    if not proj_dir.exists():
        return jsonify({"ok": False, "error": "项目不存在"}), 404
    global _workflow_process
    with _process_lock:
        if _workflow_process is not None and _workflow_process.poll() is None:
            return jsonify({"ok": False, "error": "工作流正在运行，请先停止"}), 409
    shutil.rmtree(str(proj_dir))
    return jsonify({"ok": True})


@app.route("/api/upload", methods=["POST"])
def api_upload():
    project = (request.form.get("project") or request.args.get("project") or "").strip()
    if not project:
        return jsonify({"ok": False, "error": "未指定项目"}), 400
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "未选择文件"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"ok": False, "error": "未选择文件"}), 400
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("pdf", "txt"):
        return jsonify({"ok": False, "error": "只支持 PDF / TXT 文件"}), 400

    proj_dir = _get_project(project)
    proj_dir.mkdir(parents=True, exist_ok=True)

    # Clear old problem and output
    for old in proj_dir.glob("题目.*"):
        old.unlink()
    output_dir = proj_dir / "output"
    if output_dir.exists():
        shutil.rmtree(str(output_dir))
    state_file = proj_dir / "state.json"
    if state_file.exists():
        state_file.unlink()
    fb_file = output_dir / "revision-feedback.json"
    if fb_file.exists():
        fb_file.unlink()

    file.save(str(proj_dir / f"题目.{ext}"))
    return jsonify({"ok": True, "filename": file.filename})


@app.route("/api/run", methods=["POST"])
def api_run():
    global _workflow_process, _current_project
    data = request.get_json(silent=True) or {}
    project = data.get("project", "").strip()
    if not project:
        return jsonify({"ok": False, "error": "未指定项目"}), 400
    if not problem_exists(project):
        return jsonify({"ok": False, "error": "请先上传题目文件"}), 400

    with _process_lock:
        if _workflow_process is not None and _workflow_process.poll() is None:
            return jsonify({"ok": False, "error": "工作流正在运行中"}), 409

        provider = data.get("provider", "")
        if provider in ("claude", "codex"):
            config = load_config()
            config["agent"]["provider"] = provider
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

        _current_project = project
        thread = threading.Thread(target=_run_workflow_bg, args=(project,), daemon=True)
        thread.start()

    return jsonify({"ok": True, "project": project})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    global _workflow_process
    with _process_lock:
        if _workflow_process is None or _workflow_process.poll() is not None:
            return jsonify({"ok": False, "error": "没有正在运行的工作流"}), 400
        try:
            _workflow_process.terminate()
            _workflow_process.wait(timeout=10)
        except Exception:
            try:
                _workflow_process.kill()
                _workflow_process.wait(timeout=5)
            except Exception:
                pass
        _workflow_process = None
    return jsonify({"ok": True})


@app.route("/api/agent", methods=["GET", "POST"])
def api_agent():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        provider = data.get("provider", "")
        if provider in ("claude", "codex"):
            config = load_config()
            config["agent"]["provider"] = provider
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return jsonify({"ok": True, "provider": provider})
        return jsonify({"ok": False, "error": "Invalid provider"}), 400

    config = load_config()
    agent = config.get("agent", {})
    return jsonify({
        "provider": agent.get("provider", "claude"),
        "available": [
            {"id": "claude", "name": "Claude Code", "desc": "Anthropic · Skills 生态"},
            {"id": "codex", "name": "Codex CLI", "desc": "OpenAI · GPT-5.3-Codex"},
        ]
    })


@app.route("/api/status")
def api_status():
    project = request.args.get("project", "")
    running = False
    with _process_lock:
        running = _workflow_process is not None and _workflow_process.poll() is None
    if project:
        return jsonify({
            "project": project,
            "state": load_state(project),
            "running": running and _current_project == project,
            "has_problem": problem_exists(project),
        })
    return jsonify({"projects": _list_projects(), "running": running})


@app.route("/api/reset", methods=["POST"])
def api_reset():
    global _workflow_process
    data = request.get_json(silent=True) or {}
    project = data.get("project", "").strip()
    if not project:
        return jsonify({"ok": False, "error": "未指定项目"}), 400

    with _process_lock:
        if _workflow_process is not None and _workflow_process.poll() is None:
            _workflow_process.terminate()
            _workflow_process = None

    proj_dir = _get_project(project)
    state_file = proj_dir / "state.json"
    if state_file.exists():
        state_file.unlink()
    output_dir = proj_dir / "output"
    if output_dir.exists():
        shutil.rmtree(str(output_dir))
    if data.get("delete_problem"):
        for old in proj_dir.glob("题目.*"):
            old.unlink()
    return jsonify({"ok": True})


@app.route("/api/stage/<int:stage_id>")
def api_stage(stage_id):
    project = request.args.get("project", "")
    config = load_config()
    stage = next((s for s in config["stages"] if s["id"] == stage_id), None)
    if not stage:
        return jsonify({"error": "Stage not found"}), 404
    content = get_stage_content(project, stage)
    state = load_state(project) if project else {}
    stage_state = state.get("stages", {}).get(str(stage_id), {})
    return jsonify({"stage": stage, "content": content, "state": stage_state})


@app.route("/api/file")
def api_file():
    project = request.args.get("project", "")
    rel_path = request.args.get("path", "")
    if not rel_path:
        return jsonify({"error": "No path"}), 400
    if project:
        filepath = (_get_project(project) / rel_path).resolve()
        root = str(_get_project(project).resolve())
    else:
        filepath = (PROJECT_DIR / rel_path).resolve()
        root = str(PROJECT_DIR.resolve())
    if not str(filepath).startswith(root):
        return jsonify({"error": "Access denied"}), 403
    if not filepath.exists():
        return jsonify({"error": "File not found"}), 404
    content = filepath.read_text(encoding="utf-8", errors="replace")
    suffix = filepath.suffix.lower()
    if suffix == ".md":
        html = markdown.markdown(content, extensions=["tables", "fenced_code"])
        return jsonify({"type": "markdown", "html": html, "raw": content})
    elif suffix == ".tex":
        return jsonify({"type": "latex", "content": content})
    elif suffix in (".py", ".json"):
        return jsonify({"type": "code", "content": content, "lang": suffix[1:]})
    return jsonify({"type": "text", "content": content})


@app.route("/api/image")
def api_image():
    project = request.args.get("project", "")
    rel_path = request.args.get("path", "")
    if project:
        filepath = (_get_project(project) / rel_path).resolve()
        root = str(_get_project(project).resolve())
    else:
        filepath = (PROJECT_DIR / rel_path).resolve()
        root = str(PROJECT_DIR.resolve())
    if not str(filepath).startswith(root):
        return "Access denied", 403
    if not filepath.exists():
        return "Not found", 404
    return send_file(str(filepath))


@app.route("/api/feedback", methods=["GET"])
def get_feedback():
    project = request.args.get("project", "")
    if not project:
        return jsonify([])
    return jsonify(load_feedback(project))


@app.route("/api/feedback", methods=["POST"])
def post_feedback():
    data = request.get_json() or {}
    project = (data.get("project") or "").strip()
    if not project:
        return jsonify({"ok": False, "error": "未指定项目"}), 400
    feedback_list = load_feedback(project)
    feedback_list.append({
        "id": len(feedback_list) + 1,
        "content": data.get("content", ""),
        "section": data.get("section", ""),
        "created_at": datetime.now().isoformat(),
        "resolved": False
    })
    save_feedback(project, feedback_list)
    return jsonify({"ok": True})


@app.route("/api/feedback/<int:fid>/resolve", methods=["POST"])
def resolve_feedback(fid):
    project = request.args.get("project", "")
    if not project:
        return jsonify({"ok": False, "error": "未指定项目"}), 400
    feedback_list = load_feedback(project)
    for item in feedback_list:
        if item["id"] == fid:
            item["resolved"] = True
            break
    save_feedback(project, feedback_list)
    return jsonify({"ok": True})


if __name__ == "__main__":
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    print("数学建模工作流 → http://localhost:5000")
    webbrowser.open("http://localhost:5000")
    app.run(debug=False, port=5000)
