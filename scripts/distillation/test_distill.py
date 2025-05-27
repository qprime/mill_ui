import sys
from pathlib import Path
import json

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from scripts.distillation.cleaner import clean_text
from scripts.distillation.distill_text import distill_text, batch_distill

# --- Example guidance block ---
default_guidance = {
    "persona": "english language distillation expert and software engineer",
    "task_type": "specification",
    "tone": "precise",
    "urgency": "medium"
}

def run_single_example():
    raw = """
this'll be my sidechat area today... So first thing I'm wondering: Can I prompt you to request additional resources only if needed?  For instance, could I teach you about a project, but not necessarily give you every file in the code project whole (maybe you just get the RAG of the functions).  Then could you request one or several original files for clarification?  If so, could I automate that to a degree?  We're doing this in the context of cliff where I control the contexts before sending to the openai api.
 """
    cleaned = clean_text(raw)
    result = distill_text(cleaned, default_guidance, strict_mode=True)
    print(json.dumps(result, indent=2))

def run_batch_example():
    input_data = [
        (
            "so yeah maybe like we add a button to mark moments in the video right?",
            {"persona": "frontend_engineer", "task_type": "code_generation", "tone": "casual", "urgency": "medium"}
        ),
        (
            "okay then we need a short summary for each voice annotation or it'll get chaotic",
            {"persona": "product_designer", "task_type": "ui_summary", "tone": "direct", "urgency": "high"}
        ),
    ]

    cleaned_batch = [(clean_text(text), guidance) for text, guidance in input_data]
    output_path = Path("scripts/distillation/sample_output.jsonl")
    batch_distill(cleaned_batch, output_path)
    print(f"✅ Batch distillation complete. Output: {output_path}")

if __name__ == "__main__":
    run_single_example()
    # run_batch_example()
