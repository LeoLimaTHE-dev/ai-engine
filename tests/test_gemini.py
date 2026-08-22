from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client()

response = client.models.generate_content(
    model="gemini-3.6-flash", contents="Reply with exactly: Gemini API is working."
)

print(response.text)
