import json
import traceback
from typing import List, Tuple
from .schemas import OrderDraft, Order, PartyDraft, OrderItemDraft, Currency, PaymentMethod
from pydantic import ValidationError
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

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
        traceback.print_exc()
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("未找到有效的 JSON 片段")
        return json.loads(raw[start:end + 1])

# 把 pydantic 的 loc 转成 "a.b[0].c" 形式
def _format_loc(loc) -> str:
    parts = []
    for p in loc:
        if isinstance(p, int):
            # 把上一个字段名换成带索引的形式
            if not parts:
                parts.append(f"[{p}]")
            else:
                parts[-1] = f"{parts[-1]}[{p}]"
        else:
            parts.append(str(p))
    return ".".join(parts)

def calc_missing(d: OrderDraft) -> List[str]:
    missing = []

    # 只问这些“对话必填项”（可按需要增减）
    if not (d.seller and d.seller.name):
        missing.append("seller.name")
    if not (d.buyer and d.buyer.name):
        missing.append("buyer.name")

    if not (d.items and len(d.items) > 0):
        missing += ["items[0].name", "items[0].qty", "items[0].unit_price"]
    else:
        it0 = d.items[0]
        if not it0.name:
            missing.append("items[0].name")
        if not it0.qty or (isinstance(it0.qty, int) and it0.qty <= 0):
            missing.append("items[0].qty")
        if not it0.unit_price:
            missing.append("items[0].unit_price")

    # 你想“明确询问”的就保留；不想问就删掉（Order 里有默认值）
    if not d.currency:
        missing.append("currency")
    if not d.payment_method:
        missing.append("payment_method")

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

def canonical_field(field: str) -> str:
    if field == "seller":
        return "seller.name"
    if field == "buyer":
        return "buyer.name"
    return field

def apply_single_answer(d: OrderDraft, field: str, text: Optional[str]) -> OrderDraft:
    t = (text or "").strip()
    field = canonical_field(field)

    # 确保子模型存在（都是 *Draft）
    if d.seller is None:
        d.seller = PartyDraft()
    if d.buyer is None:
        d.buyer = PartyDraft()
    if not d.items:
        d.items = [OrderItemDraft()]

    # ---- 填值 ----
    if field == "seller.name":
        d.seller.name = t

    elif field == "buyer.name":
        d.buyer.name = t

    elif field == "items[0].name":
        d.items[0].name = t

    elif field == "items[0].qty":
        # 允许 “5個”“3台” 等：提取数字
        digits = "".join(ch for ch in t if ch.isdigit())
        if digits:
            try:
                q = int(digits)
                if q > 0:
                    d.items[0].qty = q
            except:
                pass

    elif field == "items[0].unit_price":
        # 允许 “8,000円” “8000.00” 等：提取数字和小数点
        digits = "".join(ch for ch in t if ch.isdigit() or ch == ".")
        if digits:
            try:
                d.items[0].unit_price = Decimal(digits)
            except:
                pass

    elif field == "currency":
        # 交给 Order 的 validator 最终规范也可以；这里先做一次常见映射
        m = {"円": "JPY", "日本円": "JPY", "JPY": "JPY",
             "USD": "USD", "ドル": "USD",
             "EUR": "EUR", "ユーロ": "EUR"}
        key = t.upper()
        d.currency = m.get(key, m.get(t, t))  # 可以是 enum 名或字符串，最终由 Order 校验

    elif field == "payment_method":
        m = {"銀行振込": "BANK_TRANSFER", "振込": "BANK_TRANSFER",
             "クレジットカード": "CARD", "カード": "CARD",
             "現金": "CASH", "CASH": "CASH", "CARD": "CARD", "BANK_TRANSFER": "BANK_TRANSFER"}
        d.payment_method = m.get(t, t)

    # 返回新的 Draft（用字段名而非 alias 重建，避免键名错位）
    return OrderDraft(**d.model_dump(by_alias=False, exclude_none=True))

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

def to_order_if_complete(d: OrderDraft) -> Tuple[bool, Order | None]:
    # 还有缺失就直接 False
    if calc_missing(d):
        return False, None

    # 用字段名 dump；补默认 issue_date
    data = d.model_dump(by_alias=False, exclude_none=True)
    data.setdefault("issue_date", date.today())

    try:
        order = Order(**data)  # 严格校验（含 enum + 金额 + email 等）
        return True, order
    except ValidationError:
        traceback.print_exc()
        # 理论上这里不会触发；如果触发，说明 schema 约束比“对话必填”更严格
        return False, None




