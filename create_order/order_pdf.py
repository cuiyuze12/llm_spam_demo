from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS
from io import BytesIO
from datetime import date
import os

router = APIRouter()

# 你的真实数据获取逻辑替换这里（从内存、DB、或 session 中取）
def get_order_data(order_id: str):
    # DEMO 数据结构（根据你的 Order 模型字段改名/映射）
    return {
        "order_id": order_id,
        "order_date": date.today().strftime("%Y-%m-%d"),
        "buyer": {
            "name": "株式会社テスト",
            "department": "調達部",
            "person": "山田 太郎",
            "postal": "〒100-0001",
            "address": "東京都千代田区千代田1-1",
            "tel": "03-1234-5678",
            "email": "yamada@example.co.jp",
        },
        "ship_to": {
            "name": "株式会社テスト 受入センター",
            "postal": "〒100-0002",
            "address": "東京都千代田区丸の内1-1",
            "tel": "03-9876-5432",
        },
        "items": [
            {"name": "ノートPC", "spec": "14inch Core i7/16GB/512GB", "qty": 2, "unit": "台", "unit_price": 120000},
            {"name": "マウス",   "spec": "無線 2.4GHz",             "qty": 5, "unit": "個", "unit_price": 2000},
        ],
        "currency": "JPY",
        "tax_rate": 0.10,  # 10% 消費税
        "remarks": "※ 納期は発注後2週間以内。検収後にお支払い。",
        "issuer": {
            "company": "Wonderlusia Solutions",
            "postal": "〒104-0045",
            "address": "東京都中央区築地1-2-3",
            "tel": "03-1111-2222",
            "email": "order@wonderlusia.site",
            "seal_box": True,  # 印影欄（飾り用の枠）
        }
    }

# Jinja2 環境
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
STATIC_DIR     = os.path.join(os.path.dirname(__file__), "..", "static")

jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"])
)

@router.get("/orders/{order_id}/pdf")
def download_order_pdf(order_id: str):
    data = get_order_data(order_id)
    if not data:
        raise HTTPException(status_code=404, detail="Order not found")

    # 金額計算（必要に応じてあなたのロジックに置き換え）
    for it in data["items"]:
        it["amount"] = it["qty"] * it["unit_price"]
    subtotal = sum(it["amount"] for it in data["items"])
    tax = int(round(subtotal * data["tax_rate"]))
    total = subtotal + tax

    data["subtotal"] = subtotal
    data["tax"] = tax
    data["total"] = total

    template = jinja_env.get_template("order_pdf.html")
    html_str = template.render(data=data)

    # base_url 指定で相対パスの静的ファイル（字体/CSS/图片）を解決
    base_url = STATIC_DIR  # 让模板里 /static/... 能被找到。也可以用项目根目录
    html = HTML(string=html_str, base_url=base_url)

    # 可选：外部 CSS
    css = CSS(string="""
      @page { size: A4; margin: 18mm 14mm; }
    """)

    pdf_io = BytesIO()
    html.write_pdf(pdf_io, stylesheets=[css])
    pdf_io.seek(0)

    filename = f"注文書_{order_id}.pdf"
    return StreamingResponse(pdf_io, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"'
    })