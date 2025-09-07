from __future__ import annotations
from pydantic import BaseModel, Field, AliasChoices, EmailStr, field_validator, ConfigDict, condecimal
from typing import List, Optional
from enum import Enum
from datetime import date

class Currency(str, Enum):
    JPY = "JPY"
    USD = "USD"
    EUR = "EUR"

class PaymentMethod(str, Enum):
    CARD = "CARD"
    BANK_TRANSFER = "BANK_TRANSFER"
    CASH = "CASH"

class Party(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # 英語キー（第一候補） + 日本語エイリアス
    name: str = Field(alias=AliasChoices("name", "名称", "会社名", "氏名"))
    email: Optional[EmailStr] = Field(default=None, alias=AliasChoices("email", "メール", "メールアドレス"))
    phone: Optional[str]      = Field(default=None, alias=AliasChoices("phone", "電話", "電話番号"))
    address: Optional[str]    = Field(default=None, alias=AliasChoices("address", "住所"))
    tax_id: Optional[str]     = Field(default=None, alias=AliasChoices("tax_id", "税番号", "法人番号", "インボイス番号"))

class OrderItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sku: str  = Field(alias=AliasChoices("sku", "SKU", "型番", "品番"))
    name: str = Field(alias=AliasChoices("name", "品名", "商品名"))
    qty: int  = Field(gt=0, alias=AliasChoices("qty", "数量", "個数", "数"))
    # 金額系は >=0 / >0 を用途に応じて調整
    unit_price: condecimal(gt=0, max_digits=12, decimal_places=2) = Field(alias=AliasChoices("unit_price", "単価", "単価（円）"))
    discount:   condecimal(ge=0, max_digits=12, decimal_places=2) = Field(default=0, alias=AliasChoices("discount", "値引", "割引"))

class Order(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    template_id: str = Field(default="invoice_default_v1", alias=AliasChoices("template_id", "テンプレート"))
    order_id: Optional[str] = Field(default=None, alias=AliasChoices("order_id", "注文番号", "請求書番号", "見積番号"))
    issue_date: date = Field(alias=AliasChoices("issue_date", "発行日"))
    due_date: Optional[date] = Field(default=None, alias=AliasChoices("due_date", "支払期日", "期日"))

    seller: Party = Field(alias=AliasChoices("seller", "売り手", "発行者", "販売者", "請求元"))
    buyer:  Party = Field(alias=AliasChoices("buyer", "買い手", "請求先", "顧客", "購入者"))

    currency: Currency = Field(default=Currency.JPY, alias=AliasChoices("currency", "通貨"))
    payment_method: PaymentMethod = Field(default=PaymentMethod.BANK_TRANSFER,
                                          alias=AliasChoices("payment_method", "支払方法", "お支払い方法"))

    items: List[OrderItem] = Field(alias=AliasChoices("items", "明細", "商品明細", "内訳"))

    tax_rate_pct: condecimal(ge=0, le=100, max_digits=5, decimal_places=2) = Field(
        default=10, alias=AliasChoices("tax_rate_pct", "消費税率", "税率")
    )
    shipping_fee: condecimal(ge=0, max_digits=12, decimal_places=2) = Field(
        default=0, alias=AliasChoices("shipping_fee", "送料", "配送料")
    )
    notes: Optional[str] = Field(default=None, alias=AliasChoices("notes", "備考", "特記事項"))

    # === 日本語値の正規化（必要に応じて拡張） ===
    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, v):
        if v is None:
            return v
        s = str(v).strip()
        mapping = {"円": "JPY", "日本円": "JPY", "JPY": "JPY",
                   "USD": "USD", "ドル": "USD",
                   "EUR": "EUR", "ユーロ": "EUR"}
        return mapping.get(s, s)

    @field_validator("payment_method", mode="before")
    @classmethod
    def normalize_payment(cls, v):
        if v is None:
            return v
        s = str(v).strip()
        mapping = {"銀行振込": "BANK_TRANSFER", "振込": "BANK_TRANSFER",
                   "クレジットカード": "CARD", "カード": "CARD",
                   "現金": "CASH"}
        return mapping.get(s, s)

    # 便利プロパティ（合計など）
    @property
    def items_total(self):
        from decimal import Decimal
        total = Decimal("0")
        for it in self.items:
            total += (it.unit_price * it.qty) - it.discount
        return total

    @property
    def tax_amount(self):
        return self.items_total * (self.tax_rate_pct / 100)

    @property
    def grand_total(self):
        return self.items_total + self.tax_amount + self.shipping_fee
