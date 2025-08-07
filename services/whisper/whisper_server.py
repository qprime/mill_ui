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
        segments, info = model.transcribe(tmp_path)
        text = " ".join([segment.text for segment in segments])
        return {"text": text}
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
