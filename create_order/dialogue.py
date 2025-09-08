from typing import List, Tuple
from .schemas import OrderDraft, Order, Currency, PaymentMethod
from pydantic import ValidationError
from datetime import date
from decimal import Decimal

# 定义“必填项”的最小集合（可按你的业务调整）
REQUIRED = [
    "buyer.name",
    "items[0].name",
    "items[0].qty",
    "items[0].unit_price",
    "currency",
    "payment_method",
]

def extract_json(raw: str) -> dict:
    """
    尝试从模型输出里提取 JSON：
    1) 先直接 json.loads
    2) 失败则截取第一个 '{' 到最后一个 '}' 的片段再 loads
    """
    if raw is None:
        raise ValueError("LLM 返回为空")
    try:
        return json.loads(raw)
    except Exception:
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("未找到有效的 JSON 片段")
        return json.loads(raw[start:end + 1])

def calc_missing(d: OrderDraft) -> List[str]:
    missing = []
    if not (d.buyer and d.buyer.name): missing.append("buyer.name")
    if not (d.items and len(d.items)>0):
        missing += ["items[0].name","items[0].qty","items[0].unit_price"]
    else:
        it0 = d.items[0]
        if not it0.name: missing.append("items[0].name")
        if not it0.qty:  missing.append("items[0].qty")
        if not it0.unit_price: missing.append("items[0].unit_price")
    if not d.currency: missing.append("currency")
    if not d.payment_method: missing.append("payment_method")
    return missing

def next_question(field: str) -> str:
    # 日文提问模板
    mapping = {
        "buyer.name": "請求先（買い手）の会社名または氏名を教えてください。",
        "items[0].name": "商品名（例：スマートフォン機種名）を教えてください。",
        "items[0].qty": "数量はいくつですか？（半角の正の整数）",
        "items[0].unit_price": "単価はいくらですか？（税抜/税込のどちらでも。半角数字、例：49800）",
        "currency": "通貨を選んでください（JPY / USD / EUR）。",
        "payment_method": "お支払い方法は？（銀行振込 / クレジットカード / 現金）",
    }
    return mapping.get(field, f"{field} を教えてください。")

def apply_single_answer(d: OrderDraft, field: str, text: str) -> OrderDraft:
    """
    只更新当前询问的字段，尽量避免“模型自由发挥”。
    这里用简单规则解析用户回答（生产中可以用一个“小范畴Prompt”，限制只返回该字段值）。
    """
    t = text.strip()

    # 初始化 items
    if (not d.items) or len(d.items)==0:
        d.items = [{}]  # 临时结构，pydantic 会在再次构造时整理

    # 简单规则填充
    if field == "buyer.name":
        d.buyer = d.buyer or {}
        d.buyer["name"] = t
    elif field == "items[0].name":
        d.items[0]["name"] = t
    elif field == "items[0].qty":
        try:
            qty = int(t.replace("個","").replace("台","").strip())
            if qty>0: d.items[0]["qty"] = qty
        except: pass
    elif field == "items[0].unit_price":
        # 只提取数字部分
        digits = "".join(ch for ch in t if ch.isdigit() or ch==".")
        if digits:
            d.items[0]["unit_price"] = str(Decimal(digits))
    elif field == "currency":
        m = {"円":"JPY","日本円":"JPY","JPY":"JPY","USD":"USD","ドル":"USD","EUR":"EUR","ユーロ":"EUR"}
        d.currency = m.get(t.upper(), m.get(t, None))
    elif field == "payment_method":
        m = {"銀行振込":"BANK_TRANSFER","振込":"BANK_TRANSFER",
             "クレジットカード":"CARD","カード":"CARD","現金":"CASH"}
        d.payment_method = m.get(t, None)
    return OrderDraft(**d.model_dump(by_alias=True, exclude_none=True))

def to_strict_order(d: OrderDraft) -> Order:
    """
    将 Draft（字段允许为 None）转换为严格的 Order。
    要求 Draft 已经补全了所有必填；这里做最终规范化和校验。
    """
    data = d.model_dump(by_alias=True, exclude_none=True)
    # 没有 issue_date 就给今天（抽取阶段未填时）
    data.setdefault("issue_date", date.today().isoformat())
    # 交给严格的 Pydantic Order 校验
    return Order(**data)

def to_order_if_complete(d: OrderDraft) -> Tuple[bool, Order]:
    """
    字段齐全则构造严格 Order，否则返回 (False, None)。
    issue_date 没填就用今天。
    """
    if calc_missing(d): return False, None
    data = d.model_dump(by_alias=True)
    data.setdefault("issue_date", date.today().isoformat())
    try:
        order = Order(**data)
        return True, order
    except ValidationError:
        return False, None




