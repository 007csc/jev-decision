# 🎮 JEV Decision Skill

> 本地零成本结构化决策引擎（JEV System One 风格）| OpenClaw Skill

基于本地 Ollama 模型，复现 TypeSafe JEV 的「System One」决策能力。**零API费用，完全离线**，适合游戏AI实时判断、道具门卫、战斗优先级等高频系统一决策场景。

---

## ✨ 特性

- **三种决策原语**：Noul（是非概率）/ Score（有序评分）/ Choice（选项概率分布）
- **零成本**：完全本地运行，无需任何 API Key
- **离线可用**：依赖 Ollama，本地模型推理
- **置信度门控**：每条决策附带置信度，可自动分流高/低置信场景
- **即装即用**：一行命令安装，无需配置

## 适用场景

| 场景 | JEV 原语 |
|------|---------|
| 道具值不值得捡？ | Noul |
| 优先攻击哪个目标？ | Choice |
| 当前危险等级几分？ | Score |
| 是否应该撤退？ | Noul |
| NPC 意图判断？ | Score |
| 动作是否违规/危险？ | Noul |

## 📦 安装

### 前置要求

**1. 安装 Ollama**
```bash
# Windows: 下载安装包 https://ollama.com/download
# 或命令行
winget install Ollama.Ollama
```

**2. 下载/注册模型（二选一）**

推荐 gemma-2-2b（推荐，已针对指令微调优化）：
```bash
ollama pull gemma:2b-instruct
ollama create gemma2-2b-local -f ./Modelfile   # 如用本地 GGUF
```

或使用 qwen2.5（中文支持更好）：
```bash
ollama pull qwen2.5:3b
```

**3. 启动 Ollama 服务**
```bash
ollama serve
```

### 安装 Skill

通过 OpenClaw / SkillHub：
```bash
skillhub install jev-decision
```

或手动安装：将本仓库克隆到 `~/.openclaw/skills/jev-decision`。

---

## 🚀 使用

### 在 OpenClaw 中直接触发

在对话中描述你的判断需求，例如：

> 「帮我判断：当前玩家血量 30/100，3个敌人逼近，是否需要立即操作？」

> 「分析战斗优先级：近战兵血低但距离近，远程兵正在读条，背包有血瓶。先打哪个？」

### Python API

```python
import sys
sys.path.insert(0, "path/to/zerocost_jev.py")
from zerocost_jev import ZeroCostJevClient, Noul, Choice, Score

client = ZeroCostJevClient(model="gemma2-2b-local", timeout=300)
result = client.system_one(
    state="玩家血量30/100，前方3个敌人逼近",
    questions={
        "urgent": Noul(instructions="当前局面是否紧急需要立即处理？"),
        "target": Choice(
            instructions="优先攻击哪个目标？",
            criteria={
                "melee": "近战兵(血量低)",
                "ranged": "远程兵(正在读条)",
                "potion": "先捡血瓶",
                "retreat": "先撤退"
            }
        ),
        "danger": Score(
            instructions="综合危险等级",
            criteria=["安全", "较低", "中等", "较高", "危急"]
        )
    }
)
print(result)
```

### 命令行

```bash
# 快速判断
python scripts/decision.py quick '{"state":"玩家血量30/100，敌人逼近","instructions":"是否紧急？"}'

# 完整多题
python scripts/decision.py full '{
  "state": "战斗场景描述",
  "questions": {
    "target": {
      "type": "choice",
      "instructions": "优先攻击哪个",
      "criteria": {"nearest": "最近的", "lowest": "血量最低的", "boss": "BOSS"}
    }
  }
}'
```

---

## 🏗️ 架构

```
用户对话
    ↓ (OpenClaw 识别触发词)
JEV Decision Skill
    ↓
zerocost_jev.py (决策引擎)
    ↓ (HTTP, 绕过代理)
本地 Ollama (gemma2-2b-local)
    ↓
结构化 JSON 决策结果
    ↓
用户 / AI 下一步判断
```

**核心技术借鉴：**
- [TypeSafe AI / system-one-adapter-python](https://github.com/typesafe-ai/system-one-adapter-python) — state+questions API 形态
- [Yinsongxu / LLM2Jev](https://github.com/Yinsongxu/LLM2Jev) — prefill 概率引擎思路
- [TypeSafe JEV](https://typesafe.ai) — System One 决策模型理念

---

## 📊 输出示例

```json
{
  "answers": {
    "urgent": {"type": "noul", "noul": 0.8, "confidence": 0.9},
    "target": {
      "type": "choice",
      "choice": "nearest",
      "probabilities": {"nearest": 0.6, "lowest_hp": 0.2, "boss": 0.1, "retreat": 0.1},
      "confidence": 0.9
    },
    "danger": {"type": "score", "score": 2.5, "confidence": 0.9}
  },
  "model": "gemma2-2b-local",
  "usage": {"prompt_tokens": 425}
}
```

---

## 🔧 配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `model` | gemma2-2b-local | Ollama 模型名 |
| `timeout` | 300 | 单题超时（秒，CPU慢） |
| `temperature` | 0.0 | 推理温度 |

修改 `scripts/decision.py` 顶部的 `MODEL` / `TIMEOUT` 常量即可。

---

## ⚠️ 已知限制

- **CPU 推理较慢**：单题 60~300 秒（取决于模型和硬件）
- **概率为估计值**：非真 logit softmax（无 logprobs），为 prompt 结构化概率估计
- **需要 Ollama 运行中**：首次使用前确保 `ollama serve` 在后台运行

---

## 🤝 贡献

欢迎提交 Issue 和 PR！特别欢迎：
- 更多模型适配（Qwen2.5、Llama3 等）
- 概率校准优化
- 游戏场景扩展
- Benchmark 对比测试

---

## 📄 许可证

MIT License

---

*本项目是独立开源实现，与 TypeSafe AI 无附属关系。*
