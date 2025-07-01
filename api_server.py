from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import random
import torch.nn.functional as F
import matplotlib.pyplot as plt
import os
import csv
from inference import predict
from finetuned_model.load_classifier import load_model_and_tokenizer, classify_review
from training_model.train_classifier import train_model

app = FastAPI()

# 静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 应用启动时加载一次模型和 tokenizer
model, tokenizer, device = load_model_and_tokenizer()

# === 输入模型格式 ===
class TextInput(BaseModel):
    text: str

# 请求体模型
class PredictRequest(BaseModel):
    text: str

# 响应体模型（可选）
class PredictResponse(BaseModel):
    label: str
    confidence: float

# === 首页 ===
@app.get("/")
def read_index():
    return FileResponse("static/index.html")

# 挂载整个 static 目录（可选：用于支持 css, js）
app.mount("/static", StaticFiles(directory="static"), name="static")

# === 推理API ===
@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    predicted_label, confidence_score = classify_review(req.text, model, tokenizer, device)
    return PredictResponse(label=predicted_label, confidence=confidence_score)

# === 模型再训练API ===
@app.post("/train")
async def train_model(file: UploadFile = File(...)):
    # 假设上传的是 CSV 格式：text,label（0/1）
    contents = await file.read()
    acc = run_training(contents)

    return JSONResponse(content={"message": f"訓練完了：正解率 = {acc:.2f}"})

@app.get("/download-training-data")
async def download_training_data():
    # 确保 sample_train_data.csv 存在
    filepath = "static/sample_train_data.csv"
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("text,label\n")
            f.write("Congratulations, you won a free ticket!,1\n")
            f.write("Hi, just checking in on our meeting.,0\n")
            f.write("Earn money fast by clicking here!,1\n")
            f.write("Are you available for a call tomorrow?,0\n")

    return FileResponse(filepath, filename="sample_train_data.csv", media_type="text/csv")