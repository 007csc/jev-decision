# -*- coding: utf-8 -*-
"""
JEV结构化决策 - Skill 入口脚本
=================================
接收 JSON 参数（stdin 或命令行），调用 zerocost_jev.py，返回结构化决策结果。

用法:
  python decision.py quick '{"state":"...","instructions":"...","type":"noul"}'
  python decision.py '{"state":"...","questions":{...}}'
"""
import sys
import json
import os

# 将 workspace 添加到 Python 路径，以便 import zerocost_jev
WORKSPACE = r"C:\Users\Administrator\.qclaw\workspace-main"
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

from zerocost_jev import ZeroCostJevClient, Noul, Choice, Score

MODEL = "gemma2-2b-local"
TIMEOUT = 300  # CPU 推理慢，放宽超时


def _build_question(q_name, q_data):
    qtype = q_data.get("type", "")
    instructions = q_data.get("instructions", "")
    criteria = q_data.get("criteria")
    if qtype == "noul":
        return Noul(instructions=instructions, criteria=criteria)
    elif qtype == "choice":
        return Choice(instructions=instructions, criteria=criteria)
    elif qtype == "score":
        return Score(instructions=instructions, criteria=criteria)
    else:
        raise ValueError(f"未知问题类型: {qtype}")


def _format_result(result):
    """将 JEV 返回结果格式化为易读输出。"""
    lines = ["\n=== JEV 结构化决策结果 ==="]
    for name, ans in result.get("answers", {}).items():
        qtype = ans.get("type", "")
        conf = ans.get("confidence", 0)
        conf_bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
        lines.append(f"\n【{name}】({qtype})")

        if qtype == "noul":
            noul = ans.get("noul", 0)
            label = "是" if noul >= 0.5 else "否"
            lines.append(f"  概率: {noul:.2f} → {label}")
            lines.append(f"  置信度: {conf:.2f} [{conf_bar}]")

        elif qtype == "score":
            score = ans.get("score", 0)
            lines.append(f"  分值: {score:.2f}")
            lines.append(f"  置信度: {conf:.2f} [{conf_bar}]")

        elif qtype == "choice":
            probs = ans.get("probabilities", {})
            chosen = ans.get("choice", "?")
            sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
            for opt, p in sorted_probs:
                marker = " ✅" if opt == chosen else ""
                lines.append(f"  {opt}: {p:.2f}{marker}")
            lines.append(f"  置信度: {conf:.2f} [{conf_bar}]")

    lines.append(f"\n模型: {result.get('model','?')}")
    lines.append(f"Token: {result.get('usage',{}).get('prompt_tokens','?')}")
    return "\n".join(lines)


def run_quick(args):
    """快速单题接口。"""
    state = args.get("state", "")
    instructions = args.get("instructions", args.get("statement", ""))
    qtype = args.get("type", "noul")

    if qtype == "noul":
        questions = {"quick": Noul(instructions=instructions)}
    elif qtype == "choice":
        criteria = args.get("criteria", {"A": "选项A", "B": "选项B"})
        questions = {"quick": Choice(instructions=instructions, criteria=criteria)}
    elif qtype == "score":
        criteria = args.get("criteria", ["低", "中", "高"])
        questions = {"quick": Score(instructions=instructions, criteria=criteria)}
    else:
        print(json.dumps({"error": f"不支持的类型: {qtype}"}))
        sys.exit(1)

    client = ZeroCostJevClient(model=MODEL, timeout=TIMEOUT)
    result = client.system_one(state=state, questions=questions)
    return result


def run_full(args):
    """完整 system_one 接口，支持多题。"""
    state = args.get("state", "")
    questions_raw = args.get("questions", {})
    questions = {k: _build_question(k, v) for k, v in questions_raw.items()}

    client = ZeroCostJevClient(model=MODEL, timeout=TIMEOUT)
    result = client.system_one(state=state, questions=questions)
    return result


def main():
    # 读取输入（优先级：环境变量 > stdin > 命令行参数）
    raw = None
    cmd = "full"

    # 方式1：环境变量 JEV_JSON（OpenClaw Skill 推荐方式，零引号问题）
    if os.environ.get("JEV_JSON"):
        raw = os.environ["JEV_JSON"]
        if len(sys.argv) > 1:
            cmd = sys.argv[1]
        else:
            cmd = "full"

    # 方式2：命令行参数（json 文件路径）
    elif len(sys.argv) > 1:
        cmd = sys.argv[1]
        if len(sys.argv) > 2:
            arg = sys.argv[2]
            if os.path.isfile(arg):
                with open(arg, encoding="utf-8") as f:
                    raw = f.read().strip()
            else:
                raw = arg
        else:
            raw = None

    # 方式3：stdin
    if not raw:
        stdin_data = sys.stdin.read().strip() if not sys.stdin.isatty() else None
        raw = stdin_data

    if not raw:
        print(json.dumps({"error": "用法:\n  python decision.py quick  # 环境变量 JEV_JSON 传参\n  python decision.py quick /path/to/input.json  # 文件传参"}))
        sys.exit(1)

    # 解析 JSON（容错）
    try:
        args = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"JSON 解析失败: {e}", "raw": raw[:200]}))
        sys.exit(1)

    # 执行
    try:
        if cmd == "quick":
            result = run_quick(args)
        else:
            result = run_full(args)
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    # 输出格式
    # stdout 输出 JSON（供 Skill 解析）
    # 格式化输出到 stderr（供调试/人工查看）
    print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stdout)
    formatted = _format_result(result)
    print(formatted, file=sys.stderr)


if __name__ == "__main__":
    main()
