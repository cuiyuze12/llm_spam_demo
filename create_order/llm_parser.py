import json
from datetime import date
from pydantic import ValidationError
from .schemas import Order, OrderDraft
from .dialogue import extract_json, calc_missing, to_order_if_complete, to_strict_order
from langchain_aws import ChatBedrock
import boto3
from botocore.exceptions import BotoCoreError, ClientError

SYSTEM_JA = """\
あなたはユーザーの日本語の注文依頼から、厳密なJSONのOrderDraftオブジェクトを
**抽出**するアシスタントです。**決して架空の値を作らない**でください。

- 出力はJSONのみ。説明やコードブロックは禁止。
- JSONのキーは必ず英語（下記スキーマと一致）。値は日本語可。
- **ユーザーの入力に存在しない情報は、絶対に生成しない。**
  - 不明な項目は null にするか、省略する。
- items[].qty は正の整数。不明なら null。
- 価格/SKU/住所/電話/会社名/税番号など、ユーザーが言っていなければ null。
- もし不足情報があれば、"missing_fields": ["buyer.name", "items[0].unit_price", ...] に列挙。
- issue_date は入力がなければ null（サーバ側で補完する）。

スキーマ（OrderDraft）:
{
  "template_id": "invoice_default_v1",
  "issue_date": "YYYY-MM-DD (optional)",
  "due_date": "YYYY-MM-DD (optional)",
  "seller": {"name": "...(optional)", "email": "...(optional)", "phone": "...(optional)", "address": "...(optional)", "tax_id": "...(optional)"},
  "buyer":  {"name": "...(optional)", "email": "...(optional)", "phone": "...(optional)", "address": "...(optional)", "tax_id": "...(optional)"},
  "currency": "JPY|USD|EUR (optional)",
  "payment_method": "CARD|BANK_TRANSFER|CASH (optional)",
  "items": [
    {"sku": "...(optional)", "name": "...(optional)", "qty": 1, "unit_price": 1000.00 (optional), "discount": 0 (optional)}
  ],
  "tax_rate_pct": 10.0 (optional),
  "shipping_fee": 0 (optional),
  "notes": "...(optional)",
  "missing_fields": ["..."]  // 抽出できなかった必須候補
}

"""

USER_TEMPLATE_JA = """\
ユーザー依頼:
{request}

上記スキーマに従い、JSONのみ出力してください。
"""

# 从环境变量读取，便于在不同环境切换
BEDROCK_REGION = "us-east-1"
MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"

# 懒加载客户端（模块级单例）
_bedrock_rt = None
def _bedrock_client():
    global _bedrock_rt
    if _bedrock_rt is None:
        _bedrock_rt = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    return _bedrock_rt

def call_llm(prompt: str) -> str:
    """
    使用 Amazon Bedrock 的 Anthropic Messages API 调用 Claude。
    - 使用 SYSTEM_JA 作为 system 提示
    - 优先尝试 response_format={"type":"json_object"} 以强制 JSON 输出
    - 若该模型/版本不支持，上游报错时自动回退为普通文本并由上层做 JSON 抽取
    返回：模型输出的字符串（预期为严格 JSON）
    """
    body_base = {
        "anthropic_version": "bedrock-2023-05-31",  # 固定版本标识
        "max_tokens": 2000,
        "temperature": 0,                            # 为确保结构化稳定，设低温
        "system": SYSTEM_JA,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ],
    }

    # 先尝试开启“仅JSON对象”输出
    body_json = dict(body_base)
    body_json["response_format"] = {"type": "json_object"}

    client = _bedrock_client()

    def _invoke(request_body: dict) -> str:
        resp = client.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body),
        )
        payload = json.loads(resp["body"].read())  # Bedrock 返回流，需 .read()
        # Anthropic Messages API: 文本位于 content[0].text
        return payload["content"][0]["text"]

    # 尝试 1：强制 JSON 输出
    try:
        return _invoke(body_json)
    except (ClientError, BotoCoreError, KeyError, IndexError, TypeError, json.JSONDecodeError):
        # 尝试 2：去掉 response_format 的保守回退
        try:
            return _invoke(body_base)
        except Exception as e:
            # 统一抛出让上层处理（上层已有 {...} 截取与 Pydantic 校验兜底）
            raise RuntimeError(f"Bedrock invoke failed: {e}")

def parse_order_from_text(request_text: str) -> Order:
    raw = call_llm(USER_TEMPLATE_JA.format(request=request_text))
    data = extract_json(raw)

    draft = OrderDraft(**data)  # ← 允许很多字段为 None

    return draft