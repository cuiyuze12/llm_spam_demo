from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, Response
from fastapi.encoders import jsonable_encoder
from starlette.concurrency import run_in_threadpool
from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML, CSS
from pathlib import Path
from io import BytesIO
from datetime import date
import os
from urllib.parse import quote
from .schemas import Order

# 选择你的 PDF 引擎：
USE_WEASYPRINT = True  # 如果想换 xhtml2pdf，把这个设为 False 并看下方注释


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
env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(['html', 'xml'])
)

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

    order_id = str(order_id)  # 确保是字符串
    ascii_name = f"order_{order_id}.pdf"
    utf8_name = quote(f"注文書_{order_id}.pdf")  # URL 编码, 全 ASCII

    headers = {
        # RFC 5987: ASCII 回退 + UTF-8 真正文件名
        "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"
    }

    return StreamingResponse(pdf_io, media_type="application/pdf", headers=headers)


@router.post("/orders/pdf")
async def create_order_pdf(order: Order):
    # 1) 渲染 HTML
    try:
        template = env.get_template("order.html.j2")
        html_str = template.render(order=jsonable_encoder(order))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"template render error: {e}")

    # 2) 生成 PDF（阻塞 → 放到线程池）
    if USE_WEASYPRINT:
        def _make_pdf(html_text: str) -> bytes:
            return HTML(string=html_text, base_url=str(TEMPLATES_DIR)).write_pdf()
        try:
            pdf_bytes = await run_in_threadpool(_make_pdf, html_str)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"pdf generate error: {e}")
    else:
        # 使用 xhtml2pdf 的示例
        # def _make_pdf(html_text: str) -> bytes:
        #     dest = BytesIO()
        #     pisa_status = pisa.CreatePDF(html_text, dest=dest, encoding='utf-8')
        #     if pisa_status.err:
        #         raise RuntimeError("xhtml2pdf failed")
        #     return dest.getvalue()
        # pdf_bytes = await run_in_threadpool(_make_pdf, html_str)
        raise HTTPException(status_code=500, detail="xhtml2pdf path disabled")

    # 3) 返回 PDF
    filename = f"order_{order.order_id}.pdf"
    headers = {
        # 兼容非 ASCII 文件名
        "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)