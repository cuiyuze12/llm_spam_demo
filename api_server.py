from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import random
from inference import predict
from finetuned_model.load_classifier import load_model_and_tokenizer, classify_review

app = FastAPI()

# 应用启动时加载一次模型和 tokenizer
model, tokenizer, device = load_model_and_tokenizer()

# 请求体模型
class PredictRequest(BaseModel):
    text: str

# 响应体模型（可选）
class PredictResponse(BaseModel):
    label: str
    confidence: float

@app.get("/")
def read_index():
    return FileResponse("static/index.html")

# 挂载整个 static 目录（可选：用于支持 css, js）
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    predicted_label, confidence = classify_review(req.text, model, tokenizer, device)
    return PredictResponse(label=predicted_label, confidence)

