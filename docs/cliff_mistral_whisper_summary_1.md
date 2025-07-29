CLIFF-AI Project: Whisper + Mistral + Web Interface Integration Summary

Project Goal

Create a lightweight local system that:

Captures voice input (via local Whisper server)

Transcribes audio to text (Whisper Tiny/Medium model)

Routes transcription to local Mistral LLM (quantized, running on CPU)

Displays the response in a simple web interface (push-to-talk + response text)

This forms the Phase 1 core for CLIFF-AI's "brain" and voice command capabilities.

Components

Hardware:

Beelink EQ R6 AI Mini PC

AMD Ryzen 9 6900HX

32GB DDR5 RAM

1TB PCIe 4.0 SSD

Ubuntu 24.04 LTS

Jetson Nano

Runs slower Whisper server for distributed capture (optional, secondary node)

New Skytech Chronos PC (incoming)

Intel Core i7-13700K

RTX 4070 GPU

32GB DDR5 RAM

Future heavy-duty node for training and inference

Software:

Whisper (Local FastAPI server on Jetson Nano, optional second instance on Beelink)

Mistral 7B Instruct v0.2

Quantized using OpenVINO (INT8 model, CPU optimized)

OpenVINO Runtime

Model inference engine on CPU (no GPU requirement)

Transformers + Optimum Libraries

For model loading and tokenization

Simple Web Framework (planned)

Flask / FastAPI / Starlette for quick web app

Key Achievements

✅ Whisper server operational and accepting local audio files for transcription.

✅ Local Mistral 7B model quantized successfully (OpenVINO INT8).

✅ Mistral model tested with real prompts; small prompt latency (~7s generation time on Beelink).

✅ Quantized model and tokenizer are loading cleanly without GPU dependencies.

✅ Full pipeline tested manually: text in -> text out (no hallucination).

✅ RAM usage confirmed stable (~900MB post load, ~15GB post inference during peak on Beelink).

Lessons Learned

Whisper large or Mistral full precision are not feasible on Jetson Nano due to memory/CPU limits.

OpenVINO models must be loaded correctly; OpenVINO's CPU support was critical.

Quantizing with bitsandbytes wasn't viable on non-NVIDIA GPUs (Beelink = AMD).

Optimum + OpenVINO flow proved clean and reproducible for low-memory environments.

Running large LLMs without a GPU is slow, but viable for CLIFF-style short command pipelines.

Push-to-talk and short input enforcement will massively improve real-world usability.

Remaining Tasks (Immediate)



Future Expansion Possibilities

Stream audio continuously (instead of file upload) for near-instant voice recognition.

Integrate small intent recognition model to better route commands.

Upgrade to using Mistral 7B on new Skytech Chronos PC (GPU-accelerated for instant responses).

Add multi-mic capture (distributed satellites around house/shop).

Add CLI/SSH/API command execution based on voice triggers.

Create memory system for CLIFF to "recall" past commands, interactions, summaries.

Status Summary

Component

Status

Whisper (Nano/Beelink)

✅ Operational

Mistral Quantized Model

✅ Operational

Local Testing

✅ Complete

Web App Interface

🛠️ In Progress

Full CLIFF-AI Phase 1 Core

🚀 Ready to Assemble

Final Notes

You now have:

Local offline Whisper transcription.

Local lightweight LLM reasoning (Mistral 7B INT8).

All the base components ready to start CLIFF-AI's active voice-driven brain.

Next step: wire them into a web/voice input loop and start evolving CLIFF-AI toward full autonomy.

This milestone lays the foundation for everything coming next.

📄 End of CLIFF-AI Whisper + Mistral Phase 1 Summary Document


