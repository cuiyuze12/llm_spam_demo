from fastapi import FastAPI
from pydantic import BaseModel
import random
from inference import predict
from load_classifier import load_model_and_tokenizer, classify_review

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
def read_root():
    return {"message": "Hello from FastAPI on EC2!"}

@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    predicted_label = classify_review(req.text, model, tokenizer, device)
    return PredictResponse(label=predicted_label, confidence=0.9)

