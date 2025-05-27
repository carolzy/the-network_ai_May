# Debugging purposes
def print_agent_history(history):
    # Access (some) useful information
    print(history.urls())              # List of visited URLs
    print(history.screenshots())       # List of screenshot paths
    print(history.action_names())     # Names of executed actions
    print(history.extracted_content())  # Content extracted during execution
    print(history.errors())         # Any errors that occurred
    print(history.model_actions())     # All actions with their parameters
    print(history.final_result())


def test_openai_connection():
    import os
    import openai

    client = openai.OpenAI(
        api_key="042ca35c-beaf-4f5b-8033-9170556e5251",
        base_url="https://api.sambanova.ai/v1",
    )

    response = client.chat.completions.create(
        model="DeepSeek-R1",
        messages=[{"role": "system", "content": "You are a helpful assistant"}, {
            "role": "user", "content": "Hello"}],
        temperature=0.1,
        top_p=0.1
    )
    print(response.choices[0].message.content)
