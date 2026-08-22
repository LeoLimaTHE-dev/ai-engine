from dotenv import load_dotenv
from google import genai


def main():
    load_dotenv()
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents="Reply with exactly: Gemini API is working.",
    )
    print(response.text)


if __name__ == "__main__":
    main()
