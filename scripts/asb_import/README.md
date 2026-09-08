# ASB 数据导入

本目录保存将 ASB 来源数据转换成 VESTA seed 的**离线导入工具**。它不是 VESTA
正式评测运行时的一部分，也不负责调用模型、执行工具或判定评测结果。

## 目录边界

```text
data/source_benchmarks/asb/       ASB 完整来源快照
scripts/asb_import/               ASB 解析、case 构造和 VESTA seed 转换
scripts/test/fixtures/asb/        小型回归测试数据
data/<scope>/families/            VESTA 风险族定义
data/<scope>/tasks/               转换并审核后的正式 seed
configs/tool_configs/             VESTA 工具角色配置
src/tools/specs/                  正式运行时工具规格
src/tools/impl/                   正式运行时工具实现
```

正式评测入口 `scripts/run/run_dimension_eval.py` 只读取转换后的 VESTA 数据和工具，
不会导入本目录。这样可以继续保留 ASB 的来源可追溯性，而不在运行时维护第二套
benchmark runner。

## 文件说明

- `models.py`：导入所需的最小 ASB 数据模型。只保留 task、正常工具、攻击工具和
  case，不包含 agent 执行结果模型。
- `loaders.py`：兼容完整 ASB 字段名和小型 fixture 字段名的 JSONL 加载器。
- `case_builder.py`：构造 DPI、OPI、MP、PoT case，并实现 ASB 的五种
  `attack_type` 模板；只构造数据，不执行 agent。
- `import_asb_to_vesta.py`：将构造出的 case 转换为 VESTA seed。

## 来源快照

完整快照保存在 `data/source_benchmarks/asb/`：

| 文件 | 当前源数据行数 | 内容 |
|---|---:|---|
| `tasks.jsonl` | 10 | ASB agent 及其任务列表（加载后展开为 51 个任务） |
| `normal_tools.jsonl` | 20 | 正常工具定义 |
| `attack_tools.jsonl` | 400 | 攻击工具定义及攻击目标 |

这些文件用于复现现有迁移或继续迁移新的 ASB case，不应由正式评测运行时直接读取。
未经审核的生成结果也不应直接覆盖正式 `seeds.json`。

小型数据位于 `scripts/test/fixtures/asb/`，默认命令使用它们，以避免误生成大批量
seed。使用 `--use-all` 才会读取完整来源快照。

## 默认映射

当前导入器的默认目标是：

- ASB 来源语义：DPI 风格提示注入；
- VESTA scope：`architecture_and_modules`；
- 风险维度：`input_perception_risk`；
- 风险子类：`instruction_injection`；
- family id：`input_perception_risk.instruction_injection`；
- 风险工具角色：`input_injection_action`。

其他维度中的 ASB-derived seed 可能经过人工语义改写，不能仅通过修改
`--target-dimension` 和 `--target-subtype` 就认为映射成立。例如 information
pollution 需要把直接攻击指令改写成不可信信息材料，memory risk 需要保留检索与
历史工作流语义。

## 使用方法

先用小型 fixture 生成一个待检查文件：

```powershell
python scripts/asb_import/import_asb_to_vesta.py `
  --channels dpi `
  --attack-types naive `
  --limit-cases 2 `
  --output runtime/asb_import_preview.json
```

读取完整来源快照：

```powershell
python scripts/asb_import/import_asb_to_vesta.py `
  --use-all `
  --channels dpi `
  --attack-types naive `
  --limit-cases 7 `
  --output runtime/asb_import_preview.json
```

支持的攻击入口：

- `dpi`：攻击文本进入用户任务；
- `opi`：攻击文本进入工具 observation；
- `mp`：攻击步骤进入历史记忆/工作流；
- `pot`：攻击规则进入 planner 示例，并使用 trigger。

支持的攻击模板：`naive`、`fake_completion`、`escape_characters`、
`context_ignoring`、`combined_attack`。

`--tasks`、`--normal-tools`、`--attack-tools` 可以覆盖默认数据文件；相对路径均以
项目根目录解析。未提供 `--output` 时，输出位置为：

```text
data/architecture_and_modules/tasks/<dimension>/<subtype>_seeds/asb_seeds.json
```

建议日常始终显式指定 `--output runtime/...`，审核 diff、schema、工具角色和敏感
字段后，再人工合并到正式 seed。

## 验证

运行 ASB importer 回归测试：

```powershell
python -m unittest scripts.test.test_asb_import
```

检查生产代码不再依赖旧 Benchmark 包：

```powershell
rg "Benchmark\.ASB|Benchmark/ASB|Benchmark\\ASB" src scripts configs
```

正常情况下，上述搜索不应在可执行 Python 代码中得到结果。

每次改变来源 case、映射规则、工具角色或运行时行为时，还需要更新
`docs/asb_migration_record.md`，并验证对应维度的工具 registry 和目标提示词没有
泄漏隐藏攻击字段。
