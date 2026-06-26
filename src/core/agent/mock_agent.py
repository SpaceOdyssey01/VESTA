from src.core.agent.base import BaseAgent
from src.core.agent.schema import AgentResponse, AgentStepInput, ToolCall


class MockFinanceAgent(BaseAgent):
    def __init__(self, name: str = "mock_finance_agent"):
        super().__init__(name=name)

    def act(self, step_input: AgentStepInput) -> AgentResponse:
        step_count = len(step_input.history)

        if step_count == 0:
            return AgentResponse(
                response_type="tool_call",
                tool_call=ToolCall(
                    tool_name="check_balance",
                    arguments={"account_name": "default"}
                )
            )

        if step_count == 1:
            return AgentResponse(
                response_type="tool_call",
                tool_call=ToolCall(
                    tool_name="get_payees",
                    arguments={}
                )
            )

        if step_count == 2:
            bill_amount = step_input.environment_state.get("bill_amount", 0)
            payees = step_input.environment_state.get("payees", [])

            payee = ""
            if len(payees) > 0:
                payee = payees[0]

            return AgentResponse(
                response_type="tool_call",
                tool_call=ToolCall(
                    tool_name="make_payment",
                    arguments={
                        "payee": payee,
                        "amount": bill_amount
                    }
                )
            )

        return AgentResponse(
            response_type="final_answer",
            content="任务已完成。"
        )