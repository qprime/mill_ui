# cliff_ai/llm_server/llm_service.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
from model_runner import run_generation

app = FastAPI()

class GenRequest(BaseModel):
    prompt: str
    max_tokens: int = 200

@app.post("/generate")
async def generate(req: GenRequest):
    response = run_generation(req.prompt, req.max_tokens)
    return {"response": response}

