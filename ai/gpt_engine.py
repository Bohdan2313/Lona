# ai/gpt_engine.py

import os
from openai import OpenAI
from dotenv import load_dotenv
from utils.logger import log_error

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ask_gpt(prompt, system_prompt="", temperature=0.5, max_tokens=1000):
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model="gpt-5",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        log_error(f"❌ ask_gpt помилка: {e}")
        return "GPT error"
