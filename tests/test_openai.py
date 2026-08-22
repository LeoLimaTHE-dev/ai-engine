from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI()

response = client.responses.create(
    model="gpt-5", input="Reply with exactly: OpenAI API is working."
)

print(response.output_text)
