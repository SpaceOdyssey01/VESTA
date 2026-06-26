from typing import Any, Dict


class BaseEnvironment:
    def __init__(self, env_config: Dict[str, Any]):
        self.hidden_state = env_config.get("hidden_state", {})
        self.observation = env_config.get("observation", {})

    def get_state(self) -> Dict[str, Any]:
        """
        给 agent 的“可见状态”
        """
        return self.observation.copy()

    def get_hidden_state(self) -> Dict[str, Any]:
        """
        给 tool 使用的真实状态
        """
        return self.hidden_state

    def update_values(self, delta: Dict[str, Any]):
        """
        更新 hidden state
        """
        for k, v in delta.items():
            self.hidden_state[k] = v