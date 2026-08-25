from opspilot.llm import agent_decision
from opspilot.registry import ollama_tool_definitions


messages = [
    {
        "role": "system",
        "content": (
            "You are an incident investigation agent. "
            "Choose an appropriate read-only investigation tool."
        ),
    },
    {
        "role": "user",
        "content": (
            "Investigate a checkout-api latency problem. "
            "Choose the most appropriate tool to gather evidence."
        ),
    },
]


tool_definitions = ollama_tool_definitions()


response = agent_decision(
    messages=messages,
    tool_definitions=tool_definitions,
)


print("\n=== AGENT DECISION RESULT ===")
print(response)