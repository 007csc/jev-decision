# -*- coding: utf-8 -*-
"""
ZeroCostJev — 零成本 JEV 兼容决策引擎
=====================================
借鉴对象（GitHub）:
  - typesafe-ai/system-one-adapter-python  : state+questions API 形态、Noul/Score/Choice 原语、probabilities 模式
  - Yinsongxu/LLM2Jev                      : prefill 概率引擎思路（此处适配为 prompt 结构化概率估计，因 Ollama CPU 不返回 logprobs）

核心思想（与 JEV 一致 -> System One 决策模型）:
  给模型「状态(state)」+「一组带预定义答案空间的问题(questions)」，
  模型不生成自由文本，而是返回 typed 决策 + 概率 + 置信度，供代码直接分支。

后端: 本地 Ollama (OpenAI 兼容 /v1/chat/completions)，零 API 费用、可离线。
可无缝切换任何 OpenAI 兼容端点（OpenRouter / vLLM / 云端），只需改 base_url。
"""

import json
import re
import requests


# ---------------------------------------------------------------------------
# 三种问题原语（与 TypeSafe JEV 完全对齐）
# ---------------------------------------------------------------------------
class Noul:
    """是非题：返回 0~1 的概率（statement 为 true 的概率）。"""
    def __init__(self, instructions, criteria=None):
        self.type = "noul"
        self.instructions = instructions
        self.criteria = criteria  # 可选: {"true": "...", "false": "..."}


class Choice:
    """选择题：从预定义选项中选一个，返回每个选项概率 + 置信度。"""
    def __init__(self, instructions, criteria: dict):
        self.type = "choice"
        self.instructions = instructions
        self.criteria = criteria  # {label: description}


class Score:
    """评分题：在有序刻度上给一个位置（可带小数），返回位置 + 置信度。"""
    def __init__(self, instructions, criteria: list):
        self.type = "score"
        self.instructions = instructions
        self.criteria = criteria  # ["很低", "低", "中", "高", "很高"]


# ---------------------------------------------------------------------------
# 客户端
# ---------------------------------------------------------------------------
class ZeroCostJevClient:
    def __init__(self, base_url="http://localhost:11434/v1",
                 model="gemma2-2b-local", api_key="ollama",
                 temperature=0.0, timeout=120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout
        # 绕过本机代理（localhost Ollama 不应被 OpenClaw 代理拦截）
        self._no_proxy = {"http": None, "https": None}

    # ---- 对外主接口（对齐 JEV system_one）---------------------------------
    def system_one(self, state, questions: dict, model=None):
        model = model or self.model
        answers = {}
        used_tok = 0
        for name, q in questions.items():
            ans, tok = self._ask(name, q, state)
            answers[name] = ans
            used_tok += tok
        return {
            "answers": answers,
            "model": model,
            "usage": {"prompt_tokens": used_tok, "completion_tokens": 0},
        }

    # ---- 单题求解 ---------------------------------------------------------
    def _ask(self, name, q, state):
        if q.type == "noul":
            return self._ask_noul(name, q, state)
        if q.type == "choice":
            return self._ask_choice(name, q, state)
        if q.type == "score":
            return self._ask_score(name, q, state)
        raise ValueError(f"未知问题类型: {q.type}")

    def _chat(self, system_prompt, user_prompt):
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json",
                   "Authorization": f"Bearer {self.api_key}"}
        resp = requests.post(url, json=payload, headers=headers,
                             timeout=self.timeout, proxies=self._no_proxy)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        tok = usage.get("prompt_tokens", 0)
        return content, tok

    def _ask_noul(self, name, q, state):
        sys_p = ("你是结构化决策引擎。只输出 JSON，不要任何解释文字。"
                 "根据状态判断陈述句为 true 的概率 p (0~1)，并给出置信度 confidence (0~1)。"
                 "格式: {\"noul\": <float>, \"confidence\": <float>}")
        crit = ""
        if q.criteria:
            crit = (f"\n判断标准: 当 {q.criteria.get('true','')} 时为 true；"
                    f"当 {q.criteria.get('false','')} 时为 false。")
        usr = (f"【状态】\n{state}\n\n"
                f"【陈述】{q.instructions}{crit}\n\n"
                f"请输出 JSON。")
        text, tok = self._chat(sys_p, usr)
        d = self._safe_json(text)
        noul = self._clip01(d.get("noul"))
        conf = self._clip01(d.get("confidence", noul))
        return {"type": "noul", "noul": noul, "confidence": conf}, tok

    def _ask_choice(self, name, q, state):
        opts = "\n".join(f"{k}. {v}" for k, v in q.criteria.items())
        sys_p = ("你是结构化决策引擎。只输出 JSON，不要解释。"
                 "对每个选项估计概率 p_i (0~1)，并给出整体置信度 confidence (0~1)。"
                 "所有 p_i 之和应为 1。"
                 "格式: {\"probabilities\": {\"A\": <float>, ...}, \"confidence\": <float>}")
        usr = (f"【状态】\n{state}\n\n"
               f"【问题】{q.instructions}\n"
               f"【选项】\n{opts}\n\n"
               f"请估计每个选项概率并输出 JSON。")
        text, tok = self._chat(sys_p, usr)
        d = self._safe_json(text)
        probs_raw = d.get("probabilities", {}) or {}
        # 归一化
        norm = {}
        total = sum(float(v) for v in probs_raw.values()) or 1.0
        for k, v in probs_raw.items():
            norm[k] = max(0.0, float(v)) / total
        # 选最高
        best = max(norm, key=norm.get) if norm else None
        conf = self._clip01(d.get("confidence", max(norm.values()) if norm else 0.0))
        return {"type": "choice", "choice": best,
                "probabilities": norm, "confidence": conf}, tok

    def _ask_score(self, name, q, state):
        levels = "\n".join(f"{i}. {lv}" for i, lv in enumerate(q.criteria))
        sys_p = ("你是结构化决策引擎。只输出 JSON，不要解释。"
                 "在有序刻度上给出位置 score (可为小数, 范围 0~%d)，并给出置信度 confidence (0~1)。"
                 "格式: {\"score\": <float>, \"confidence\": <float>}" % (len(q.criteria) - 1))
        usr = (f"【状态】\n{state}\n\n"
               f"【问题】{q.instructions}\n"
               f"【有序刻度】\n{levels}\n\n"
               f"请给出位置并输出 JSON。")
        text, tok = self._chat(sys_p, usr)
        d = self._safe_json(text)
        n = len(q.criteria) - 1
        score = self._clip(d.get("score"), 0.0, float(n))
        conf = self._clip01(d.get("confidence", 0.5))
        return {"type": "score", "score": score,
                "confidence": conf}, tok

    # ---- 工具 -------------------------------------------------------------
    @staticmethod
    def _clip01(v):
        try:
            return max(0.0, min(1.0, float(v)))
        except Exception:
            return 0.0

    @staticmethod
    def _clip(v, lo, hi):
        try:
            return max(lo, min(hi, float(v)))
        except Exception:
            return lo

    @staticmethod
    def _safe_json(text):
        if not text:
            return {}
        text = text.strip()
        # 去代码块标记
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            text = m.group(0)
        try:
            return json.loads(text)
        except Exception:
            return {}


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------
def system_one(state, questions, **kw):
    """一行调用：system_one(state, {"q1": Noul(...), ...})"""
    return ZeroCostJevClient(**kw).system_one(state, questions)


if __name__ == "__main__":
    # 自测
    c = ZeroCostJevClient()
    r = c.system_one(
        state="玩家血量 30/100，前方出现 3 个敌人，背包有 2 个血瓶。",
        questions={
            "urgent": Noul(instructions="当前局面是否紧急，需要立即处理？"),
            "target": Choice(instructions="优先攻击哪个目标？",
                             criteria={"nearest": "最近的敌人",
                                       "lowest_hp": "血量最低的敌人",
                                       "boss": "看似头目的敌人",
                                       "ignore": "暂不交战，先撤退"}),
            "danger": Score(instructions="综合评估当前危险等级",
                            criteria=["极低", "低", "中", "高", "极高"]),
        },
    )
    print(json.dumps(r, ensure_ascii=False, indent=2))
