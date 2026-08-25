from opspilot.llm import call_llm


response = call_llm(
    [
        {
            "role": "user",
            "content": "Reply with the single word: OK",
        }
    ]
)

print(response)