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
    Okay, so I'm using the original app you gave me, not the download one. I have a feeling that if I open that, it's probably not anything real. That just hasn't worked in the past. So, I have the original one. I need to send it to my desktop, which I can do that right now. I send that to desktop, copy the email list, add to home screen. Okay, so I'm calling it tagger. Add. It's right on my home screen. I don't know if I opened it. It's opening right up. I'm still doing it locally, but let's... I don't actually see how to add a picture. I've got save. Let's see. Photo close. Okay, so it looks like I need to take a picture and then save, sort of add a photo, and add tags. That's not the end of the world. It's not the workflow I look for. But now, I guess I need to maybe turn on Wi-Fi and see if it'll still work. Yeah, just a note. What I was hoping for was something where I could take a picture from within the app, right? It'd be like, tick, tick, you know, and I'd click it, and then it would open the camera. I would take the picture, and then I went back to the app, I would take the picture, and then I went back to the app, and I would add tags. So, I'm going to turn off Wi-Fi and see if there's still a stuff. I'm a little unsure what else to find for the quick version, if this works.
    """
    cleaned = clean_text(raw)
    result = distill_text(cleaned, default_guidance)
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
    run_batch_example()
