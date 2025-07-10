from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from finetuned_model.load_classifier import load_model_and_tokenizer, classify_review
from finetuned_model.load_generator import load_generation_model, generate_text
from rag.rag_retriever import real_rag_answer
from agent.agent_chatter import run_bedrock_agent
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

app = FastAPI()

# ========== 配置 ==========
RATE_LIMIT = 60  # 每个 IP 每分钟最多请求次数
ALLOWED_PATH_PREFIX = "/api"

# ========== 内部存储 ==========
ip_access_log = {}  # 存储 IP 的访问时间戳


class RateLimitAndPathFilterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        path = request.url.path

        # ❌ 不以 /api 开头的路径禁止访问
        if not path.startswith(ALLOWED_PATH_PREFIX):
            return Response(status_code=403, content="Forbidden: Only /api/* paths are allowed.")

        # ✅ 限速逻辑
        now = time.time()
        timestamps = ip_access_log.get(client_ip, [])
        # 保留最近1分钟的请求时间
        timestamps = [t for t in timestamps if now - t < 60]

        if len(timestamps) >= RATE_LIMIT:
            return Response(status_code=429, content="Too Many Requests: Rate limit exceeded.")

        timestamps.append(now)
        ip_access_log[client_ip] = timestamps

        return await call_next(request)

# 添加中间件
app.add_middleware(RateLimitAndPathFilterMiddleware)

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

@app.post("/api/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    predicted_label, confidence_score = classify_review(req.text, model, tokenizer, device)
    return PredictResponse(label=predicted_label, confidence=confidence_score)

@app.post("/api/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    result = generate_text(req.prompt, gen_model, gen_tokenizer)
    return GenerateResponse(response=result)

# === RAG用 ===
class RAGRequest(BaseModel):
    query: str

@app.post("/api/rag_qa")
def rag_qa(req: RAGRequest):
    # ↓ あなたのRAG推論ロジックに置き換えてください
    answer = real_rag_answer(req.query)
    return {"answer": answer}

def fake_rag_answer(query: str) -> str:
    # 仮実装（あなたのretrieval+LLM生成に差し替えてOK）
    if "Honda" in query:
        return "私はHondaでプロジェクトリーダーとして、需給計画システムのソリューション選定を担当しています。"
    return f"「{query}」に関する情報は、職務経歴ドキュメントに存在しない可能性があります。"

# === Agent用 ===
class AgentRequest(BaseModel):
    message: str

@app.post("/api/agent_chat")
async def agent_chat(req: AgentRequest):
    prompt = req.message
    result = run_bedrock_agent(prompt)
    #return {"answer": answer}
    return {
        "answer": result["text"],
        "category": result["category"]
    }
