import os
from openai import OpenAI
from dotenv import load_dotenv
import google.generativeai as genai
import ollama
from groq import Groq

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
            response = open_client.chat.completions.create(
                model="gpt-5",
                messages=[{"role": "user", "content": "Say hello!"}],
                max_tokens=50,
                temperature=0.7,
            )
            print("response:", response.choices[0].message.content.strip())
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
    model = genai.GenerativeModel("gemini-3.1-flash-lite")
    try:
        response = model.generate_content("How do you say 'Alex likes men' in Spanish?")
        print("Gemini response:", response.text)
    except Exception as e:
        print("Gemini API test failed:", e)


def launch_ollama():
    try:
        response = ollama.chat(
            model="llama3",
            messages=[
                {
                    "role": "user",
                    "content": "Tell me a joke.",
                },
            ],
        )
        print("Ollama response:", response["message"]["content"])
    except Exception as e:
        print("Ollama API test failed:", e)


def launch_groq():
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        print("GROQ_API_KEY not found in environment.")
        return
    client = Groq(api_key=groq_api_key)
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": "Where do babies come from?",
                }
            ],
            model="llama-3.1-8b-instant",
        )
        print("Groq response:", chat_completion.choices[0].message.content)
    except Exception as e:
        print("Groq API test failed:", e)


def launch_openrouter():
    openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        print("OPENROUTER_API_KEY not found in environment.")
        return
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=openrouter_api_key,
    )

    free_models = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemma-4-31b-it:free",
        "liquid/lfm-2.5-1.2b-instruct:free",
        "qwen/qwen3-coder:free",
        "poolside/laguna-xs.2:free",
    ]

    for model_name in free_models:
        try:
            print(f"Trying OpenRouter model: {model_name}...")
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": "Explain the concept of quantum computing.",
                    }
                ],
            )
            print("OpenRouter response:", completion.choices[0].message.content)
            return  # Success, exit the function
        except Exception as e:
            print(f"Model {model_name} failed: {e}\n")

    print("All free OpenRouter models failed.")


# launch_openrouter()
# launch_open_ai()
# launch_gemini_ai()
# launch_ollama()
launch_groq()
