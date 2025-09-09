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

    # seller/buyer 名称
    if not (d.seller and d.seller.name):
        missing.append("seller.name")
    if not (d.buyer and d.buyer.name):
        missing.append("buyer.name")

    # items[0] 必填项（含 sku）
    if not (d.items and len(d.items) > 0):
        missing += ["items[0].sku", "items[0].name", "items[0].qty", "items[0].unit_price"]
    else:
        it0 = d.items[0]
        if not it0.sku:  missing.append("items[0].sku")
        if not it0.name: missing.append("items[0].name")
        if not it0.qty or (isinstance(it0.qty, int) and it0.qty <= 0):
            missing.append("items[0].qty")
        if not it0.unit_price:
            missing.append("items[0].unit_price")

    # 其他对话必填
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

def _enum_code(s: str) -> str:
    # ' Currency.JPY ' -> 'JPY'；'円' -> '円'（后面再映射）
    s = (s or "").strip()
    if "." in s:
        s = s.split(".")[-1]
    return s.upper()

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
        code = _enum_code_str(t)
        code = {"円":"JPY","日本円":"JPY","ドル":"USD","ユーロ":"EUR"}.get(code, code)
        d.currency = code  # 这里给代码值即可，Draft 会接受；最终构造 Order 再严格校验

    elif field == "payment_method":
        code = _enum_code_str(t)
        code = {"銀行振込":"BANK_TRANSFER","振込":"BANK_TRANSFER",
                "クレジットカード":"CARD","カード":"CARD","現金":"CASH"}.get(code, code)
        d.payment_method = code


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

def _coerce_enum_like(val, EnumType, mapping: dict):
    if val is None:
        return None
    # 已经是枚举 -> 直接返回
    try:
        from enum import Enum
        if isinstance(val, Enum):
            return val
    except Exception:
        pass
    # 字符串归一化
    s = str(val).strip()
    if "." in s:
        s = s.split(".")[-1]
    s = s.upper()
    s = mapping.get(s, s)
    try:
        return EnumType(s)   # 转成枚举实例
    except ValueError:
        return s             # 留给 Order 的 validator 再试
    
def to_order_if_complete(d: OrderDraft) -> Tuple[bool, Order | None]:
    # 还有缺失就直接 False
    missing = calc_missing(d)

    if len(missing) > 0:
        return False, None

    # 用字段名 dump；排除 Draft 专属字段，避免多余键影响
    data = d.model_dump(
        by_alias=False,
        exclude_none=True,
        exclude={"missing_fields"}   # 关键：把 Draft 的辅助字段去掉
    )
    data.setdefault("issue_date", date.today())

    # ✅ 最后一层再兜一次：把可能混进来的 'Currency.JPY' -> 'JPY'
    if isinstance(data.get("currency"), str):
        data["currency"] = _enum_code_str(data["currency"])
    if isinstance(data.get("payment_method"), str):
        data["payment_method"] = _enum_code_str(data["payment_method"])

    # （可选）再做一次日文到代码的映射
    data["currency"] = {"円":"JPY","日本円":"JPY","ドル":"USD","ユーロ":"EUR"}.get(data.get("currency",""), data.get("currency"))
    data["payment_method"] = {"銀行振込":"BANK_TRANSFER","振込":"BANK_TRANSFER",
                              "クレジットカード":"CARD","カード":"CARD","現金":"CASH"}.get(data.get("payment_method",""), data.get("payment_method"))

    try:
        order = Order(**data)  # 严格校验（含 enum + 金额 + email 等）
        return True, order
    except ValidationError:
        traceback.print_exc()
        # 理论上这里不会触发；如果触发，说明 schema 约束比“对话必填”更严格
        return False, None


# --- helpers: 归一化枚举文本 ---

def _enum_code_str(s: str) -> str:
    """把 'Currency.JPY' / 'PaymentMethod.CARD' / ' jpy ' 等规整成大写代码 'JPY' / 'CARD'。"""
    s = (s or "").strip()
    if "." in s:  # 'Currency.JPY' -> 'JPY'
        s = s.split(".")[-1]
    return s.upper()

def _normalize_draft_enums_inplace(d: dict) -> dict:
    """就地把 draft 里的 currency / payment_method 统一成 'JPY' / 'CARD' 等代码值。"""
    if "currency" in d and isinstance(d["currency"], str):
        s = _enum_code_str(d["currency"])
        # 日文别名 -> 代码
        s = {"円":"JPY","日本円":"JPY","ドル":"USD","ユーロ":"EUR"}.get(s, s)
        d["currency"] = s

    if "payment_method" in d and isinstance(d["payment_method"], str):
        s = _enum_code_str(d["payment_method"])
        s = {"銀行振込":"BANK_TRANSFER","振込":"BANK_TRANSFER",
             "クレジットカード":"CARD","カード":"CARD","現金":"CASH"}.get(s, s)
        d["payment_method"] = s

    return d


