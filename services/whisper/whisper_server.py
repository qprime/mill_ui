from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel
import tempfile
import os
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.options("/transcribe")
async def options_transcribe():
    return JSONResponse(content={"message": "CORS preflight OK"}, status_code=200)

model = WhisperModel("large-v2", compute_type="auto")

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        segments, info = model.transcribe(tmp_path, word_timestamps=True)
        text_parts = []
        segment_payload = []
        words_payload = []
        for segment in segments:
            segment_text = segment.text.strip()
            if segment_text:
                text_parts.append(segment_text)
            word_items = []
            if segment.words:
                for word in segment.words:
                    entry = {"start": word.start, "end": word.end, "word": word.word}
                    word_items.append(entry)
                    words_payload.append(entry)
            segment_payload.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment_text,
                "words": word_items
            })
        text = " ".join(text_parts).strip()
        return {"text": text, "words": words_payload, "segments": segment_payload, "language": info.language}
    finally:
        os.remove(tmp_path)


if __name__ == "__main__":
    uvicorn.run(
        "services.whisper.whisper_server:app",
        host="0.0.0.0",
        port=8001,
        ssl_keyfile="services/whisper/cert/whisper.key",
        ssl_certfile="services/whisper/cert/whisper.crt"
    )
