import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from create_order.llm_parser import parse_order_from_text
from rag.rag_retriever import real_rag_answer
from agent.agent_chatter import run_bedrock_agent
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time

from create_order.schemas import OrderDraft, Order
from create_order.dialogue import calc_missing, next_question, apply_single_answer, to_order_if_complete

from typing import List, Optional

app = FastAPI()

# ========== 配置 ==========
RATE_LIMIT = 60  # 每个 IP 每分钟最多请求次数
ALLOWED_PATH_PREFIX = "/api"

# ========== 内部存储 ==========
ip_access_log = {}  # 存储 IP 的访问时间戳

ALLOWED_PATH_PREFIXES = ["/api", "/", "/index.html", "/favicon.ico", "/static"]  # 保留主页、静态文件等

BLOCKED_PATTERNS = [".php", ".aspx", "/wp-", "/admin", "/config", "/log", "/radio"]

class RateLimitAndPathFilterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        path = request.url.path

        # ❌ 拒绝明显的攻击路径
        for pattern in BLOCKED_PATTERNS:
            if pattern in path:
                return Response(status_code=403, content=f"Forbidden: Suspicious path {path}")

        # ✅ 允许的路径前缀
        if not any(path.startswith(p) for p in ALLOWED_PATH_PREFIXES):
            return Response(status_code=403, content="Forbidden: Path not allowed.")

        # Rate Limit 限制
        now = time.time()
        timestamps = ip_access_log.get(client_ip, [])
        timestamps = [t for t in timestamps if now - t < 60]
        if len(timestamps) >= RATE_LIMIT:
            return Response(status_code=429, content="Too Many Requests: Rate limit exceeded.")
        timestamps.append(now)
        ip_access_log[client_ip] = timestamps

        return await call_next(request)

# 添加中间件
app.add_middleware(RateLimitAndPathFilterMiddleware)

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
    return FileResponse("static/index2.html")

# 挂载整个 static 目录（可选：用于支持 css, js）
app.mount("/static", StaticFiles(directory="static"), name="static")

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

# ===== 新規追加: 注文書生成 =====
class StartReq(BaseModel):
    text: str
    template_id: str = "invoice_default_v1"

class StepReq(BaseModel):
    draft: dict          # 前端携带当前的 OrderDraft JSON
    field: str           # 这次回答的是哪个字段（上次返回给你的）
    answer: str          # 用户的回答

class OrderRequest(BaseModel):
    text: str
    template_id: str = "invoice_default_v1"  # 将来扩展时可支持不同模板
    
@app.post("/agent/order/create")
def create_order(req: OrderRequest):
    """
    ユーザーの日本語依頼テキストを受け取り、注文書の構造化JSONを生成して返す。
    """
    try:
        order = parse_order_from_text(req.text)
        # Pydanticモデルのdictを返すと自動でJSONシリアライズされる
        return order.model_dump()
    except Exception as e:
        # 打印完整的 stack trace 到控制台/日志
        traceback.print_exc()
        # 如果你想把堆栈信息作为字符串保存，可以这样：
        # error_trace = traceback.format_exc()
        # print(error_trace)
        raise HTTPException(status_code=500, detail=f"注文書生成に失敗しました: {str(e)}")

@app.post("/agent/order/start")
def order_start(req: StartReq):
    """
    第一次解析：把自然语言转为 OrderDraft，并给出第一个问题。
    """
    try:
        draft = parse_order_from_text(req.text)  # 这里请让 parse 返回 OrderDraft（上一条已给）
        if isinstance(draft, OrderDraft) is False:
            # 如果你的 parse 仍返回严格 Order，也可以先转成 Draft；建议直接改 parse 返回 Draft
            draft = OrderDraft(**draft.model_dump())
        missing = calc_missing(draft)
        if not missing:
            done, order = to_order_if_complete(draft)
            if done: return {"status":"done", "order": order.model_dump()}
        field = missing[0]
        return {
            "status": "ask",
            "question": next_question(field),
            "field": field,
            "draft": draft.model_dump(by_alias=True, exclude_none=True, mode="json")
        }
    except Exception as e:
        # 打印完整的 stack trace 到控制台/日志
        traceback.print_exc()
        raise HTTPException(500, f"解析失败: {e}")

@app.post("/agent/order/reply")
def order_reply(req: StepReq):
    """
    后续轮次：只填当前字段，生成新的 draft；若已齐全则返回最终 order。
    """
    try:
        draft = OrderDraft(**req.draft)
        draft2 = apply_single_answer(draft, req.field, req.answer)

        # 计算缺失项
        missing = calc_missing(draft2)

        # 1) 还有缺失 → 继续问下一个字段
        if missing:  # 非空才取 missing[0]
            field = missing[0]
            return {
                "status": "ask",
                "question": next_question(field),
                "field": field,
                "draft": draft2.model_dump(by_alias=True, exclude_none=True, mode="json"),
            }

        # 2) 看是否已经可以生成最终订单
        done, order = to_order_if_complete(draft2)
        if done:
            return {"status":"done", "order": order.model_dump(by_alias=True, mode="json")}

        # 3) 防御式兜底：
        #    如果 missing 为空但仍未 done，说明 calc_missing 与 to_order_if_complete 存在不一致或数据异常
        return {
            "status": "ask",
            "question": "入力を確認できませんでした。もう一度ご回答ください。",
            "field": req.field,  # 或者给个固定的首要字段，如 "buyer.name"
            "draft": draft2.model_dump(by_alias=True, exclude_none=True, mode="json"),
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"更新失败: {e}")