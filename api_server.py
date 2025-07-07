from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from finetuned_model.load_classifier import load_model_and_tokenizer, classify_review
from finetuned_model.load_generator import load_generation_model, generate_text
from rag.rag_retriever import real_rag_answer
from agent.agent_chatter import run_bedrock_agent

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
    data = await req.json()
    prompt = data.get("prompt", "")
    response = run_bedrock_agent(prompt)
    return {"response": response}

def fake_agent_response(msg: str) -> str:
    # 仮のエージェントロジック（LangChain AgentやBedrock Agentに置き換えてOK）
    if "プロジェクト" in msg:
        return "最近のプロジェクトでは、自作のLLMとRAGを組み合わせた履歴検索チャットボットを開発しました。"
    return f"エージェントは「{msg}」に対応しました（これは仮の応答です）。"