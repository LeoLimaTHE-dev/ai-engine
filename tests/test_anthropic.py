from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic()

message = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=100,
    messages=[
        {"role": "user", "content": "Reply with exactly: Claude API is working."}
    ],
)

print(message.content[0].text)
