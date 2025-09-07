# demo_test.py
import json
from datetime import date
from pydantic import ValidationError

import create_order.llm_parser as llm_parser
from create_order.schemas import Order

def run_end_to_end_ok():
    user_text = """請求書を作成してください。買い手はABC商事…（略）"""
    llm_json_ok = {
        "template_id": "invoice_default_v1",
        "issue_date": date.today().isoformat(),
        "seller": {"name": "株式会社テスト商事", "address": "東京都港区", "email": "seller@example.com"},
        "buyer":  {"name": "ABC商事", "address": "東京都中央区", "email": "buyer@example.com"},
        "currency": "JPY",
        "payment_method": "BANK_TRANSFER",
        "items": [
            {"sku": "JET-ORIN-NANO-8G", "name": "Jetson Orin Nano 8GB", "qty": 3, "unit_price": "49800.00", "discount": "0"},
            {"sku": "PSU-120W", "name": "ACアダプタ 120W", "qty": 1, "unit_price": "3000.00", "discount": "0"},
        ],
        "tax_rate_pct": "10.0",
        "shipping_fee": "0",
        "notes": "9/30までに納品",
    }

    original_call_llm = llm_parser.call_llm
    llm_parser.call_llm = lambda prompt: json.dumps(llm_json_ok)
    try:
        order = llm_parser.parse_order_from_text(user_text)
        print("✅ End-to-end OK")
        print(order.model_dump())
        print("items_total:", order.items_total)
        print("tax_amount:", order.tax_amount)
        print("grand_total:", order.grand_total)
    finally:
        llm_parser.call_llm = original_call_llm

def run_end_to_end_bad():
    user_text = "請求書を作成してください（テスト：不正データ）。"
    llm_json_bad = {
        "template_id": "invoice_default_v1",
        "issue_date": date.today().isoformat(),
        "seller": {"name": "株式会社テスト商事"},
        "buyer":  {"name": "XYZ商事"},
        "currency": "JPY",
        "payment_method": "BANK_TRANSFER",
        "items": [
            {"sku": "MON-27IN", "name": "モニター27インチ", "qty": -1, "unit_price": "-300.00"}  # 故意错误
        ],
        "tax_rate_pct": "10.0",
        "shipping_fee": "0",
    }

    original_call_llm = llm_parser.call_llm
    llm_parser.call_llm = lambda prompt: json.dumps(llm_json_bad)
    try:
        try:
            _ = llm_parser.parse_order_from_text(user_text)
            print("❌ Unexpected: should fail but passed.")
        except ValidationError as e:
            print("✅ BAD case caught ValidationError")
            print(e)
    finally:
        llm_parser.call_llm = original_call_llm

def run_alias_only_demo():
    j = {
      "発行日": date.today().isoformat(),
      "売り手": {"会社名": "株式会社テスト商事"},
      "買い手": {"会社名": "ABC商事"},
      "通貨": "日本円",
      "支払方法": "銀行振込",
      "明細": [
        {"SKU": "JET-ORIN-NANO-8G", "商品名": "Jetson Orin Nano 8GB", "数量": 3, "単価": "49800.00"},
        {"SKU": "PSU-120W", "商品名": "ACアダプタ 120W", "数量": 1, "単価": "3000.00", "値引": "0"}
      ],
      "消費税率": "10.0",
      "送料": "0",
      "備考": "別送品あり"
    }
    order = Order(**j)
    print("✅ Alias-only demo OK")
    print(order.model_dump())
    print("grand_total:", order.grand_total)

if __name__ == "__main__":
    run_end_to_end_ok()
    print("-" * 60)
    run_end_to_end_bad()
    print("-" * 60)
    run_alias_only_demo()
