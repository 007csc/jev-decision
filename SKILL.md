---
name: JEV结构化决策引擎
slug: jev-decision
displayName: JEV结构化决策引擎
description: 本地零成本的结构化决策引擎（JEV System One 风格），基于本地 Ollama 模型，支持 Noul/Score/Choice 三种原语决策。触发场景：游戏AI实时判断、道德困境评估、风险等级、优先级选择、决策评估、置信区间等。
version: 1.0.0
triggers:
  - JEV判断
  - 结构化决策
  - 游戏决策
  - 风险等级
  - 优先级选择
  - 决策评估
  - 置信区间
  - 应该行动吗
  - 选择哪个目标
  - 紧急程度判断
---

# JEV结构化决策引擎（Skill）

## 能力概述

基于本地 Ollama 模型（如 gemma2-2b）的零成本结构化决策引擎，完整复刻 TypeSafe JEV 的 System One 决策能力。

**三种决策原语：**
- **Noul（是否）**：返回 0~1 概率（如"是否逃跑？"）
- **Score（评分）**：返回有序刻度评分（如"风险等级 0~4"）
- **Choice（选择）**：返回选项概率分布（如"优先打哪个目标"）

**特点：** 不生成自由文本，直接返回 typed 决策+概率+置信度，零 API 费用，完全离线。

## 执行接口

### 命令格式
```
python scripts/decision.py <json_string>
```

JSON 参数格式：
```json
{
  "mode": "noul|score|choice",
  "question": "是否应该攻击BOSS？",
  "options": ["攻击BOSS", "攻击小怪", "逃跑", "忽略"],
  "state": "当前HP=80, 怪物数量=1小怪, BOSS血量=20%"
}
```

### 环境变量输入（推荐）
```bash
$env:JEV_JSON = '{"mode":"noul","question":"紧急吗？","state":"HP=90, 小怪=1"}'
python scripts/decision.py
```

### stdin 输入
```bash
echo '{"mode":"noul","question":"紧急吗？","state":"HP=90"}' | python scripts/decision.py
```

## 输出格式

```json
{
  "mode": "noul",
  "result": 0.2,
  "confidence": 0.9,
  "reasoning": "HP=90较高，单个小怪威胁低"
}
```

## 依赖

- Python 3.8+
- requests
- Ollama 运行中（默认 http://localhost:11434）
- 本地模型（默认 gemma2-2b:latest）

## 模型配置

修改 `scripts/decision.py` 顶部的 `OLLAMA_URL` 和 `MODEL_NAME` 可切换模型。

推荐模型：gemma2-2b、qwen2.5:0.5b、llama3.2:1b（越小越快，越大越准）
