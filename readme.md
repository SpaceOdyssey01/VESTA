# Evaluation Workflow

所有命令默认在项目根目录运行：

```bash
cd /mnt/home/jialu/X
```

## 1. Run 评测

评测结果固定输出到：

```text
outputs/results/<dimension>/<subtype>/<model>/
  results.json
  errors.json
  run_config.json
```

重跑同一个 `dimension/subtype/model` 会覆盖对应目录。

### 单模型 smoke test

```bash
python scripts/run/run_dimension_eval.py \
  --dimension supervision_control_failure \
  --subtypes interruption_failure \
  --target-llm-config configs/llm/gpt-4o-mini.yaml \
  --authority-modes soft \
  --limit 1
```

### 单进程串行跑所有模型

```bash
python scripts/run/run_dimension_eval.py \
  --dimension supervision_control_failure \
  --subtypes interruption_failure \
  --all-target-models \
  --authority-modes soft hard \
  --max-turns 4
```

### 并行跑所有模型

```bash
python scripts/run/run_dimension_models_parallel.py \
  --dimension supervision_control_failure \
  --subtypes interruption_failure \
  --authority-modes soft hard \
  --max-turns 4 \
  --max-workers 4 \
  --case-workers 2
```

这里有两层并行：

```text
--max-workers   外层并行数：同时跑多少个 dimension/model job
--case-workers  内层并行数：每个 job 内同时跑多少条 seed instance
```

例如 `--max-workers 4 --case-workers 2` 表示最多同时有 `4 x 2 = 8` 条 case 在跑。

### 并行跑指定模型

```bash
python scripts/run/run_dimension_models_parallel.py \
  --dimension supervision_control_failure \
  --subtypes interruption_failure \
  --models gpt-4o-mini gpt-5.4 claude-haiku-4-5 \
  --authority-modes soft hard \
  --max-turns 4 \
  --max-workers 3 \
  --case-workers 2
```

### 多个维度并行

```bash
python scripts/run/run_dimension_models_parallel.py \
  --dimensions supervision_control_failure goal_norm_misalignment \
  --authority-modes soft hard \
  --max-turns 4 \
  --max-workers 6 \
  --case-workers 2
```

### 所有已接线维度并行

显式传 `--all-dimensions` 可以跑所有可运行维度。未指定模型时默认跑 `configs/llm/*.yaml` 下所有模型：

```bash
python scripts/run/run_dimension_models_parallel.py \
  --all-dimensions \
  --authority-modes soft hard \
  --max-turns 4 \
  --max-workers 6 \
  --case-workers 2
```

### 推荐日常命令

先小样本 smoke test：

```bash
python scripts/run/run_dimension_models_parallel.py \
  --dimension supervision_control_failure \
  --subtypes interruption_failure \
  --models gpt-4o-mini \
  --authority-modes soft \
  --limit 1 \
  --max-workers 1 \
  --case-workers 1
```

确认正常后再扩大并行：

```bash
python scripts/run/run_dimension_models_parallel.py \
  --dimension supervision_control_failure \
  --models gpt-4o-mini gpt-5.4 claude-haiku-4-5 \
  --authority-modes soft hard \
  --max-turns 4 \
  --max-workers 3 \
  --case-workers 3
```

如果要先看会启动哪些命令，不真正运行：

```bash
python scripts/run/run_dimension_models_parallel.py \
  --dimensions supervision_control_failure goal_norm_misalignment \
  --models gpt-4o-mini gpt-5.4 \
  --max-workers 4 \
  --case-workers 2 \
  --dry-run
```

注意：总并发约等于 `--max-workers * --case-workers`，不要一下开太大，避免 API 限流或本地资源被打满。

## 2. Score 汇总

对某个维度汇总 score：

```bash
python scripts/run/score_dimension_results.py \
  --input outputs/results/supervision_control_failure \
  --output-dir outputs/results/supervision_control_failure/scores \
  --include-errors
```

输出：

```text
outputs/results/<dimension>/scores/scores.csv
outputs/results/<dimension>/scores/scores.json
```

score 会递归读取：

```text
outputs/results/<dimension>/<subtype>/<model>/results.json
outputs/results/<dimension>/<subtype>/<model>/errors.json
```

## 3. Plot 画图

```bash
python scripts/run/plot_dimension_scores.py \
  --input outputs/results/supervision_control_failure/scores/scores.csv \
  --dimension supervision_control_failure \
  --output-dir outputs/figures/supervision_control_failure
```

默认按子维度各画一张图。

常用指标：

```bash
--metric attack_success_rate
--metric unsafe_rate
--metric risk_score
--metric avg_tool_calls
```

例如：

```bash
python scripts/run/plot_dimension_scores.py \
  --input outputs/results/supervision_control_failure/scores/scores.csv \
  --dimension supervision_control_failure \
  --metric unsafe_rate \
  --output-dir outputs/figures/supervision_control_failure
```

## 4. Audit 二次审计

审计某个维度的结果目录：

```bash
python scripts/run/audit_eval_results.py \
  --input_path outputs/results/supervision_control_failure \
  --output_dir outputs/audit
```

默认使用：

```text
configs/eval_configs/claude-opus-4-7.yaml
```

审计输出按维度/子维度分开：

```text
outputs/audit/<dimension>/<subtype>.json
outputs/audit/<dimension>/<subtype>.summary.json
outputs/audit/<dimension>/summary.json
outputs/audit/summary.json
```

## 5. 新维度接线 Checklist

生成新维度 seed 后，通常需要检查这些文件：

```text
data/single_agent/tasks/<dimension>/<subtype>_seeds/seeds.json
data/single_agent/families/<dimension>/<subtype>.json
configs/tool_configs/<dimension>.yaml
src/tools/specs/<dimension>_tools.json
src/tools/impl/<dimension>_tools.py
scripts/run/run_dimension_eval.py
src/targets/single_agent_safety_prompt_builder.py
src/judgers/dispatcher.py
```

关键点：

1. `run_dimension_eval.py` 里登记 `DIMENSION_SUBTYPES`
2. `configs/tool_configs/<dimension>.yaml` 指向 tool spec 和 impl
3. tool impl 里有 `get_tool_registry()` 和 `call_tool()`
4. PromptBuilder 隐藏 judge/internal 字段
5. 先用 `--limit 1` 跑 smoke test
6. 再用 parallel 脚本跑所有模型
7. 最后单独 score、plot、audit

## 6. Tool Builder 流程

tool builder 部分的大致流程：

1. 读取 `seed.tool_manifest.required_tool_roles`
2. 根据 `configs/tool_configs/<dimension>.yaml` 做 role -> tool 映射
3. 检查这些 tool 是否都存在于：
   - `src/tools/specs/<dimension>_tools.json`
   - `src/tools/impl/<dimension>_tools.py`
4. 如果缺失：
   - 自动生成 spec
   - 自动生成 impl 方法
   - 自动检查命名、参数、`tool_type`、`risk_level`、`risk_event` 是否合法
5. 校验通过后：
   - 自动合并到正式 spec 文件
   - 自动合并到正式 impl 文件
   - 自动更新 config `role_mapping`
6. 同时在 `outputs/runtime/logs/tool_builder/<dimension>/` 写入记录

## 7. Tool Bundle Smoke Test

检查某个 seed 的 tool bundle 能否正常构建：

```bash
python -c "import json; from src.tools.builder.dimension_tool_builder import build_tool_bundle_for_instance; d=json.load(open('data/single_agent/tasks/supervision_control_failure/interruption_failure_seeds/seeds.json', encoding='utf-8')); b=build_tool_bundle_for_instance(d['instances'][0]); print(b['risk_subtype']); print(b['tool_names']); print('generated', b['generated_tools'])"
```

## 8. Evaluation Scripts

现在使用拆开的运行、打分、画图脚本：

```text
run_dimension_eval.py 或 run_dimension_models_parallel.py
score_dimension_results.py
plot_dimension_scores.py
audit_eval_results.py
```
