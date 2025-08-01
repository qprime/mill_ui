"""
[AI core]
TODO: describe module functionality.
"""

import re 
from typing import Optional 
from ai_core .client import get_chat_completion 

DISTILLER_MODEL ="gpt-4.1-mini"

SYSTEM_PROMPT ="""
You are a technical distillation engine.
Your ONLY job is to extract technical facts, actions, or key content *already present* in the input.

Output ONLY the extracted content between these markers:

<<<DISTILL_START
... distilled content here ...
DISTILL_END>>>

Do NOT generate summaries, answers, or any content outside these markers.

If you cannot extract any technical content, return the original input text as the distilled content. Do NOT reply with 'N/A', 'none', 'no content', or any blank or placeholder value.

"""

def extract_distilled_block (text :str )->Optional [str ]:
    m =re .search (r'<<<DISTILL_START\s*(.*?)\s*DISTILL_END>>>',text ,re .DOTALL )
    if not m :
        return None 
    content =m .group (1 ).strip ()
    if not content or content .lower ()in {"na","n/a","none","na.","n.a."}:
        return None 
    return content 

def distill_text(input_text, guidance=None, strict_mode=False):
    """
    Returns distilled technical content or the original input.
    - Never returns empty string or NA/none markers.
    - If no technical content is found, falls back to input and sets 'bypassed': True.
    """
    prompt = SYSTEM_PROMPT + f"\n\nInput: '{input_text}'\nOutput:"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Input: '{input_text}'\nOutput:"}
    ]
    try:
        print("CALLING get_chat_completion with:", messages)
        resp = get_chat_completion(messages, model=DISTILLER_MODEL, temperature=0.0)
        print("RECEIVED:", resp)
        content = extract_distilled_block(resp)
        if not content:
            print("DISTILLATION: EMPTY BLOCK or NA—returning original text")
            return {
                "distilled_text": input_text,
                "metadata": {"bypassed": True, "fallback": True}
            }
        print("DISTILLATION:", content)
        return {"distilled_text": content, "metadata": {"bypassed": False}}
    except Exception as e:
        print(f"EXCEPTION in distill_text: {e}")
        return {
            "distilled_text": input_text,
            "metadata": {"bypassed": True, "error": str(e), "fallback": True}
        }

