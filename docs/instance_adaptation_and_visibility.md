# ASB 实例适配与目标可见信息标准

适用范围：默认 `seeds.json` 中的 497 条实例，其中 56 条为旧格式 ASB 数据。该变更影响后续运行，不修改原始 seed 或历史结果。

## 旧格式适配

`src/core/instance_adapter.py::normalize_instance` 识别 `ASB_POT` 和 `ASB_ACTION_TOOL_CALLING` 且缺少 `target_spec` 的实例，并添加规范字段：

| 规范字段 | 原始来源 |
|---|---|
| `instance_id` | `id` |
| `domain` | `agent` |
| `family_id` | dimension + subtype |
| `target_spec.task_context` | `triggered_task`，其次 `original_task`、`instruction` |
| `environment_state` | `environment` 副本 |
| `judge_spec` | 原始安全行为、成功标准、失败信号及完整隐藏原始参考 |
| `attacker.objective` | `attacker_goal_original` |
| `attacker.initial_message` | `attacker_instruction` |

这些旧导出的 `attack_goal` 经常以 “Do not execute” 开头，实际描述安全目标，因此不作为攻击者目标或工具执行结果。PoT 的触发任务和原始规划示例保留，介绍这些示例为“投毒”的作者注释不向目标暴露。

适配器不修改输入，重复调用不会再次转换；新格式实例不做迁移。评测文件加载和 runner 均接入适配，直接调用提示构建、攻击者和 judge 的公开执行方法也支持旧实例。原始字段继续保留供审计与工具实现使用。

## 目标可见标准

策略位于 `src/targets/visibility.py`，统一用于全部 scope；任务输入与后续工具观察都经过同一私有字段过滤。

允许：业务任务、角色、执行后果、权限提示、原始消息、攻击载荷、规划示例、工具功能、签名与权限记录、协议轨迹、状态冲突和真实业务限制。

隐藏：风险分类、场景分类标题、来源 benchmark、预期安全/危险答案、judge 参考、风险事件、作者预设的风险诊断、内部执行判分标记，以及 `hidden_`、`unsafe_`、`asb_`、`risk_` 前缀字段。

外部环境和协议 seed 的分类式任务描述改为中性检查任务；包含分类名的合成操作 ID 统一呈现为 `pending-operation`。原始具体触发情境以 `reported_condition` 保留，权限、签名、资源状态等证据不因其显示问题而删除。

工具名称中的特定基准诊断词和 ASB 分类后缀改为中性别名。工具列表、观察记录与模型响应解析共用映射；内部执行、轨迹、风险标记和 judge 仍使用原工具名。别名冲突按列表顺序稳定消解。旧 ASB 工具优先展示原始工具文档，避免把生成的分类后缀当作功能描述。

这是字段边界和已知合成文本的投影规则，不是对所有自由文本的语义脱敏。不会全局删除攻击文本中的风险词，也没有重写现有模拟工具的固定验证结论；状态机真实性和正常对照样本仍是后续评测设计工作。

## 本地验证

```powershell
python -m unittest scripts.test.test_instance_visibility scripts.test.test_asb_import
```

覆盖全部 497 条 seed 的 soft/hard 提示、56 条旧实例的源数据保留及攻击/判分参考、全部实例的工具别名往返、旧实例工具注册与执行、直接 runner 调用及实际操作证据保留。模型调用使用 mock，不消耗 API。

历史测评分数使用旧提示和旧数据适配方式，不能直接作为本次变更后的基线；重新测评时应使用新的输出目录，避免断点续跑跳过已有案例。

新 runner 结果带有 `target_visibility_version: "2"`，用于识别本次提示策略。
