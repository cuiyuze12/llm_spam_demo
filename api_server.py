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
    texts, labels = [], []
    contents = await file.read()
    lines = contents.decode("utf-8").splitlines()
    reader = csv.reader(lines)
    for row in reader:
        if len(row) == 2:
            texts.append(row[0])
            labels.append(int(row[1]))

    # 简单统计准确率（模拟训练）
    correct = 0
    for text, label in zip(texts, labels):
        pred_label, _ = classify_review(text, model, tokenizer, device)
        correct += (pred_label == "spam" if label == 1 else pred_label == "not spam")

    acc = correct / len(texts)

    # 保存训练结果图像
    os.makedirs("static", exist_ok=True)
    plt.figure()
    plt.title("Accuracy")
    plt.bar(["accuracy"], [acc])
    plt.ylim(0, 1)
    plt.savefig("static/train_result.png")
    plt.close()

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