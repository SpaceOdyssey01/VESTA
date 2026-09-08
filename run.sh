#smoke test
python scripts/run/run_dimension_models_parallel.py --dimension supervision_control_failure --subtypes interruption_failure --models gpt-4o-mini --authority-modes soft --limit 1 --max-workers 1 --case-workers 1

#run
python scripts/run/run_dimension_models_parallel.py --dimensions autonomy_authority_failure goal_norm_misalignment interaction_understanding_failure robustness_generalization_failure supervision_control_failure --models deepseek-v4-pro --authority-modes soft hard --max-turns 4 --max-workers 1 --case-workers 2 --rerun-existing

#sum result
python scripts/run/score_dimension_results.py --input outputs/results --output-dir outputs/results/scores --include-errors

#draw
python scripts/run/plot_dimension_scores.py --input outputs/results/scores/scores.csv --output-dir outputs/figures/all_single_agent --metric attack_success_rate


python scripts/run/run_dimension_models_parallel.py --dimensions input_perception_risk --models gpt-4o-mini --authority-modes soft hard --max-turns 4 --max-workers 1 --case-workers 2
python scripts/run/run_dimension_models_parallel.py --dimensions input_perception_risk memory_module_risk reasoning_planning_risk action_tool_calling_risk --models gpt-4o-mini --authority-modes soft hard
python scripts\run\run_dimension_models_parallel.py --dimension multi_agent_system --models gpt-5.6-luna --authority-modes soft --max-turns 4 --max-workers 1 --case-workers 2