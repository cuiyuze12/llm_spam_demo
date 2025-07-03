from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from finetuned_model.load_classifier import load_model_and_tokenizer, classify_review
from finetuned_model.load_generator import load_generation_model, generate_text

app = FastAPI()

# 应用启动时加载一次模型和 tokenizer
model, tokenizer, device = load_model_and_tokenizer()

# 加载生成模型
gen_model, gen_tokenizer = load_generation_model()

# 请求体模型
class PredictRequest(BaseModel):
    text: str

# 响应体模型（可选）
class PredictResponse(BaseModel):
    label: str
    confidence: float

class GenerateRequest(BaseModel):
    prompt: str

class GenerateResponse(BaseModel):
    response: str

@app.get("/")
def read_index():
    return FileResponse("static/index.html")

# 挂载整个 static 目录（可选：用于支持 css, js）
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    predicted_label, confidence_score = classify_review(req.text, model, tokenizer, device)
    return PredictResponse(label=predicted_label, confidence=confidence_score)

@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    result = generate_text(req.prompt, gen_model, gen_tokenizer)
    return GenerateResponse(response=result)
