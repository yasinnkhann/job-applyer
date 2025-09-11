import os
from openai import OpenAI
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()


def launch_open_ai():
    open_api_key = os.environ.get("OPENAI_API_KEY")
    open_client = OpenAI(api_key=open_api_key)

    if open_api_key:
        try:
            models = open_client.models.list()
            print(
                "OpenAI API key is valid. Number of models available:", len(models.data)
            )
            # Test a language model response with gpt-4o
            response = open_client.chat.completions.create(
                model="gpt-5",
                messages=[{"role": "user", "content": "Say hello!"}],
                max_tokens=50,
                temperature=0.7,
            )
            print("gpt-4o response:", response.choices[0].message.content.strip())

            # response = open_client.responses.create(
            #     model="gpt-5",
            #     input="Write a one-sentence bedtime story about a unicorn.",
            # )
            # print("response:", response)
        except Exception as e:
            print("OpenAI API key test failed:", e)
    else:
        print("OPENAI_API_KEY not found in environment.")


def launch_gemini_ai():
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        print("GEMINI_API_KEY not found in environment.")
        return

    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    try:
        response = model.generate_content("How do you Alex likes men in spanish")
        print("Gemini response:", response.text)
    except Exception as e:
        print("Gemini API test failed:", e)


# launch_open_ai()
launch_gemini_ai()
