import os
import requests
import openai

# Configuration
LOCAL_LLM_URL = "http://localhost:11434/generate"
OPENAI_MODEL = "gpt-4o"

def ask_llm(prompt: str, max_tokens=300) -> str:
    """Try local Mistral first, then fallback to GPT-4o if needed."""
    try:
        res = requests.post(LOCAL_LLM_URL, json={"prompt": prompt, "max_tokens": max_tokens}, timeout=20)
        res.raise_for_status()
        output = res.json().get("response", "").strip()

        if not output or len(output.split()) < 5:
            raise ValueError("Local LLM response too weak.")
        return output

    except Exception as local_error:
        print("⚠️ Local LLM failed or insufficient:", local_error)

        try:
            openai.api_key = os.getenv("OPENAI_API_KEY")
            #print (openai.api_key)
            res = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens
            )
            return res.choices[0].message.content.strip()

        except Exception as fallback_error:
            print("❌ Fallback to GPT-4o failed:", fallback_error)
            return "I wasn’t able to answer this with either model."


