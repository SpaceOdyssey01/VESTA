# ASB-Benchmark
可用400种攻击工具，选择攻击类型进行攻击


不依赖原AIOS/pyopenagi框架，只保留可复用的benchmark：

- 正常任务集
- 正常工具 / 攻击工具 schema
- ASB 五种 `attack_type` prompt 包装方式
- DPI / OPI / MP / PoT 四种攻击入口
- 执行 runner
- 基于执行轨迹的简单 evaluator

## 目录

```text
ASB-Benchmark/
  asb_benchmark/
    schemas.py        # 数据结构
    templates.py      # five attack_types
    injectors.py      # DPI / OPI / MP / PoT
    tools.py          # simulated normal/attacker tools
    adapters.py       # mock adapter + 接入真实 agent 的接口
    evaluator.py      # attack/task success 判断
    runner.py         # 组合 benchmark case 并运行
    cli.py            # 命令行入口
  examples/
    tasks.jsonl
    normal_tools.jsonl
    attack_tools.jsonl
```

## 快速运行

在 `bench/ASB-Benchmark` 目录下：

```bash
python -m asb_benchmark.cli --demo
```

用内置的 `MockAgentAdapter` 跑一个演示，不调用真实模型。真实项目接入时，需要实现 `AgentAdapter.run()`，把 `BenchmarkCase` 转换成实际agent调用。

## ASB 攻击入口映射

| ASB 攻击 | 注入位置 | 本模块 |
|---|---|---|
| DPI | 用户输入 prompt | `DirectPromptInjector` |
| OPI | 工具 observation / retrieval result | `ObservationPromptInjector` |
| MP | memory / vector DB / history | `MemoryPoisoningInjector` |
| PoT | planner prompt / few-shot workflow examples | `PlanOfThoughtBackdoorInjector` |

## 五种 attack_type

| attack_type | 含义 |
|---|---|
| `naive` | 直接插入攻击指令 |
| `fake_completion` | 伪造任务已完成，再插入攻击指令 |
| `escape_characters` | 使用换行/格式逃逸原上下文 |
| `context_ignoring` | 要求忽略之前指令 |
| `combined_attack` | 组合 fake completion 和 context ignoring |

## 接入自己的 agent

实现一个 adapter：

```python
from asb_benchmark.adapters import AgentAdapter
from asb_benchmark.schemas import BenchmarkCase, AgentRunResult

class MyAgentAdapter(AgentAdapter):
    def run(self, case: BenchmarkCase) -> AgentRunResult:
        # 1. 用 case.injected_task 作为用户输入
        # 2. 用 case.tools 注册工具
        # 3. 如果是 OPI，把 case.observation_suffix 接到工具返回层
        # 4. 如果是 MP，把 case.memory_context 写入/注入记忆上下文
        # 5. 如果是 PoT，把 case.planner_context 加入 planner prompt
        # 6. 返回 messages/tool_calls/final_output
        ...
```

然后：

```python
from asb_benchmark.runner import BenchmarkRunner

runner = BenchmarkRunner.from_jsonl(
    tasks_path="examples/tasks.jsonl",
    normal_tools_path="examples/normal_tools.jsonl",
    attack_tools_path="examples/attack_tools.jsonl",
)
results = runner.run(adapter=MyAgentAdapter())
```

