# 风险热力图

入口：`scripts/run/plot_risk_heatmap.py`。只读取原始结果，不调用模型 API，也不修改评测结果。
依赖沿用 `requirements.txt` 中的 Matplotlib 和 NumPy。

## 三个模型的外部环境一级风险子类（默认）

默认每行只显示一级风险维度，不展开具体二级子类。外部环境共 5 行，全范围共 23 行。

```powershell
python scripts/run/plot_risk_heatmap.py --models kimi-k2.5 qwen3.6-plus doubao-seed-1-8 --scopes external_environment --output-dir outputs/figures/risk_heatmap/external_environment
```

## 全范围一级风险维度

```powershell
python scripts/run/plot_risk_heatmap.py --models kimi-k2.5 qwen3.6-plus doubao-seed-1-8 --level dimension --output-dir outputs/figures/risk_heatmap/all_dimensions
```

## 分别绘制 Soft / Hard

```powershell
python scripts/run/plot_risk_heatmap.py --models kimi-k2.5 qwen3.6-plus doubao-seed-1-8 --scopes external_environment --authority-modes soft
python scripts/run/plot_risk_heatmap.py --models kimi-k2.5 qwen3.6-plus doubao-seed-1-8 --scopes external_environment --authority-modes hard
```

可用参数：

- `--dimensions <维度名...>`：只看指定维度。
- `--level dimension|subtype`：默认 dimension，只画一级风险子类；显式指定 subtype 可展开二级子类。
- `--metric unsafe_rate|unsafe_tool_rate`：Unsafe 判定率或危险工具调用率。
- `--denominator valid|all`：默认 valid 排除运行错误，但保留 uncertain；all 包括错误，与旧评分口径兼容。
- `--min-valid 7`：有效样本少于 7 的格子显示灰色。
- `--rows-per-page 24`：超过行数自动分页，各页共享 0–100% 色标。
- `--results-root` / `--data-root`：原始结果根目录与种子数据根目录。
- `--models`：省略时包含结果文件中所有模型；指定顺序就是横轴顺序。
- `--dpi 200`：PNG 分辨率。

## 输出与统计口径

每次输出 PNG、矢量 PDF 和包含每格计数、比例、状态、时间戳的 CSV。
默认输出目录为 `outputs/figures/risk_heatmap`。同一目录的相同模式、层级和指标会覆盖同名图；不同筛选建议用不同输出目录。

- 行默认是一级风险维度（带所属范围），列是模型，颜色越深表示风险率越高。一级维度的风险率先合计其二级子类计数再计算，不平均各子类百分比。
- `n` = Safe + Unsafe + Uncertain；`err` = 执行错误数。
- 默认风险率 = Unsafe / n。合并 soft/hard 时先合计计数再除，不平均百分比。
- 灰色 N/A 表示缺失、全部报错或低于有效样本门槛；不能解释为安全。
- 同一实例、模型、权限模式的重复记录只计一次；有效结果优先于旧错误记录。
- 历史记录若缺少 instance_id，会警告并逐条保留，无法对它们自动去重。
- 种子文件提供尚未跑出结果的行，原始结果路径是风险层级的依据。
- 缺失/错误数量和有效样本量必须一起看；不同格子的有效样本可能不一致，图不是配对模型排名。
- 正在运行时各文件读取时间略有差异，图只是读取期间快照；若文件持续被写入或损坏，程序报错而不静默跳过。

测试：`python -m unittest discover -s scripts/test -p test_plot_risk_heatmap.py -v`
