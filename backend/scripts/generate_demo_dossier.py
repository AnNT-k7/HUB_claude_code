"""Generate a polished, synthetic four-document dossier for the 5-minute demo."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "output" / "pdf" / "demo_customer_dossier"
FONT_REGULAR = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")
FONT_ITALIC = Path(r"C:\Windows\Fonts\ariali.ttf")

CUSTOMER = "Nguyễn Thu Hà"
EMPLOYER = "Công ty TNHH Minh Phát Digital"
REFERENCE = "DEMO-IV-2026-001"
CURRENCY = "VND"
DECLARED_INCOME = 32_000_000
CONTRACT_SALARY = 28_000_000
REQUESTED_AMOUNT = 300_000_000
MONTHS = ("2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06")

NAVY = colors.HexColor("#0B1F3A")
BLUE = colors.HexColor("#1C64F2")
LIGHT_BLUE = colors.HexColor("#EAF2FF")
GREEN = colors.HexColor("#0E9F6E")
LIGHT_GREEN = colors.HexColor("#E7F8F1")
SLATE = colors.HexColor("#52667D")
LIGHT_SLATE = colors.HexColor("#F4F7FA")
LINE = colors.HexColor("#D8E1EA")
WHITE = colors.white


def money(value: int) -> str:
    return f"{value:,}".replace(",", ".") + " VND"


def register_fonts() -> None:
    for path in (FONT_REGULAR, FONT_BOLD, FONT_ITALIC):
        if not path.exists():
            raise FileNotFoundError(f"Required Vietnamese font not found: {path}")
    pdfmetrics.registerFont(TTFont("DemoArial", str(FONT_REGULAR)))
    pdfmetrics.registerFont(TTFont("DemoArial-Bold", str(FONT_BOLD)))
    pdfmetrics.registerFont(TTFont("DemoArial-Italic", str(FONT_ITALIC)))


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "Brand", parent=base["Normal"], fontName="DemoArial-Bold", fontSize=8,
            leading=10, textColor=BLUE, spaceAfter=2, uppercase=True,
        ),
        "title": ParagraphStyle(
            "Title", parent=base["Title"], fontName="DemoArial-Bold", fontSize=21,
            leading=25, textColor=NAVY, alignment=TA_LEFT, spaceAfter=5,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"], fontName="DemoArial", fontSize=9.5,
            leading=14, textColor=SLATE, spaceAfter=12,
        ),
        "section": ParagraphStyle(
            "Section", parent=base["Heading2"], fontName="DemoArial-Bold", fontSize=11,
            leading=14, textColor=NAVY, spaceBefore=8, spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"], fontName="DemoArial", fontSize=9.5,
            leading=14, textColor=NAVY,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["Normal"], fontName="DemoArial", fontSize=7.7,
            leading=10, textColor=SLATE,
        ),
        "small_bold": ParagraphStyle(
            "SmallBold", parent=base["Normal"], fontName="DemoArial-Bold", fontSize=8,
            leading=10, textColor=NAVY,
        ),
        "table_header": ParagraphStyle(
            "TableHeader", parent=base["Normal"], fontName="DemoArial-Bold", fontSize=8,
            leading=10, textColor=WHITE,
        ),
        "label": ParagraphStyle(
            "Label", parent=base["Normal"], fontName="DemoArial", fontSize=8,
            leading=10, textColor=SLATE,
        ),
        "value": ParagraphStyle(
            "Value", parent=base["Normal"], fontName="DemoArial-Bold", fontSize=9.5,
            leading=12, textColor=NAVY,
        ),
        "center": ParagraphStyle(
            "Center", parent=base["Normal"], fontName="DemoArial", fontSize=8.5,
            leading=11, textColor=NAVY, alignment=TA_CENTER,
        ),
        "right": ParagraphStyle(
            "Right", parent=base["Normal"], fontName="DemoArial", fontSize=8.5,
            leading=11, textColor=NAVY, alignment=TA_RIGHT,
        ),
    }


def page_decor(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 13 * mm, width, 13 * mm, fill=1, stroke=0)
    canvas.setFillColor(BLUE)
    canvas.rect(0, height - 14.5 * mm, width, 1.5 * mm, fill=1, stroke=0)
    canvas.setFont("DemoArial-Bold", 8)
    canvas.setFillColor(WHITE)
    canvas.drawString(18 * mm, height - 8.5 * mm, "INCOME VERIFICATION EXPERT")
    canvas.setFont("DemoArial", 7.5)
    canvas.drawRightString(width - 18 * mm, height - 8.5 * mm, "BỘ HỒ SƠ GIẢ LẬP - CHỈ DÙNG DEMO")
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.setFillColor(SLATE)
    canvas.setFont("DemoArial", 7)
    canvas.drawString(18 * mm, 9.5 * mm, f"Tham chiếu: {REFERENCE} | Không chứa dữ liệu khách hàng thật")
    canvas.drawRightString(width - 18 * mm, 9.5 * mm, f"Trang {doc.page}")
    canvas.restoreState()


def doc(path: Path, title: str) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        str(path), pagesize=A4, title=title, author="Income Verification Expert Demo",
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=24 * mm, bottomMargin=21 * mm,
    )


def heading(st: dict[str, ParagraphStyle], kicker: str, title: str, subtitle: str):
    return [
        Paragraph(kicker.upper(), st["brand"]),
        Paragraph(title, st["title"]),
        Paragraph(subtitle, st["subtitle"]),
    ]


def info_grid(st: dict[str, ParagraphStyle], rows: list[tuple[str, str]]) -> Table:
    data = []
    for index in range(0, len(rows), 2):
        cells = rows[index:index + 2]
        while len(cells) < 2:
            cells.append(("", ""))
        row = []
        for label, value in cells:
            row.append(
                Paragraph(
                    f'<font color="#52667D" size="8">{label}</font><br/>'
                    f'<font color="#0B1F3A" size="9.5"><b>{value}</b></font>',
                    st["body"],
                )
            )
        data.append(row)
    table = Table(data, colWidths=[84 * mm, 84 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_SLATE),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def data_table(st: dict[str, ParagraphStyle], headers: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    data = [[Paragraph(value, st["table_header"]) for value in headers]]
    data.extend([[Paragraph(value, st["small"]) for value in row] for row in rows])
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "DemoArial-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_SLATE]),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def parser_block(st: dict[str, ParagraphStyle], lines: list[str]) -> Table:
    text = "<br/>".join(lines)
    block = Table([[Paragraph(text, st["small"]) ]], colWidths=[168 * mm])
    block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#AFCBFA")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return block


def build_application(st: dict[str, ParagraphStyle]) -> Path:
    path = OUTPUT_DIR / "01_Don_vay_Phieu_khai_Nguyen_Thu_Ha.pdf"
    story = heading(st, "Tài liệu 01 - Loan application", "Đơn đề nghị vay và phiếu khai thu nhập", "Thông tin do khách hàng kê khai phục vụ xác minh thu nhập vay tín chấp.")
    story += [
        info_grid(st, [
            ("Họ và tên", CUSTOMER),
            ("Mã tham chiếu hồ sơ", REFERENCE),
            ("Đơn vị công tác", EMPLOYER),
            ("Sản phẩm", "Vay tín chấp cá nhân"),
            ("Số tiền vay đề nghị", money(REQUESTED_AMOUNT)),
            ("Thời hạn đề nghị", "36 tháng"),
        ]),
        Paragraph("Thông tin thu nhập kê khai", st["section"]),
        data_table(st, ["Nguồn thu nhập", "Số tiền/tháng", "Tiền tệ", "Ghi chú"], [["Lương và thu nhập thường xuyên", money(DECLARED_INCOME), CURRENCY, "Khách hàng tự kê khai"]], [58 * mm, 42 * mm, 24 * mm, 44 * mm]),
        Spacer(1, 10),
        parser_block(st, [
            f"Họ và tên: {CUSTOMER}",
            f"Đơn vị công tác: {EMPLOYER}",
            f"Thu nhập khai báo: {money(DECLARED_INCOME)}",
            f"Tiền tệ: {CURRENCY}",
        ]),
        Paragraph("Xác nhận", st["section"]),
        Paragraph("Khách hàng xác nhận thông tin trên là dữ liệu giả lập dùng riêng cho kịch bản trình diễn hệ thống xác minh thu nhập. Tài liệu không có giá trị giao dịch hoặc cấp tín dụng.", st["body"]),
        Spacer(1, 15),
        data_table(st, ["Khách hàng", "Chuyên viên tiếp nhận"], [["Nguyễn Thu Hà (giả lập)", "Linh Trần - Underwriter demo"]], [84 * mm, 84 * mm]),
    ]
    doc(path, "Đơn vay - Nguyễn Thu Hà").build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    return path


def build_contract(st: dict[str, ParagraphStyle]) -> Path:
    path = OUTPUT_DIR / "02_Hop_dong_lao_dong_Nguyen_Thu_Ha.pdf"
    story = heading(st, "Tài liệu 02 - Employment contract", "Trích lục hợp đồng lao động", "Bản trích thông tin công việc và tiền lương phục vụ xác minh hồ sơ.")
    story += [
        info_grid(st, [
            ("Người lao động", CUSTOMER),
            ("Người sử dụng lao động", EMPLOYER),
            ("Chức danh", "Chuyên viên phân tích dữ liệu"),
            ("Loại hợp đồng", "Xác định thời hạn 36 tháng"),
            ("Ngày hiệu lực", "2026-01-01"),
            ("Ngày hết hạn", "2028-12-31"),
        ]),
        Paragraph("Điều khoản công việc và tiền lương", st["section"]),
        data_table(st, ["Hạng mục", "Nội dung"], [
            ["Mức lương theo hợp đồng", money(CONTRACT_SALARY) + "/tháng"],
            ["Hình thức trả lương", "Chuyển khoản vào ngày 25 hằng tháng"],
            ["Thưởng hiệu suất", "Theo kết quả công việc, không cố định"],
            ["Tiền tệ", CURRENCY],
        ], [62 * mm, 106 * mm]),
        Spacer(1, 10),
        parser_block(st, [
            f"Khách hàng: {CUSTOMER}",
            f"Công ty: {EMPLOYER}",
            f"Lương hợp đồng: {money(CONTRACT_SALARY)}",
            "Ngày hết hạn: 2028-12-31",
            f"Tiền tệ: {CURRENCY}",
        ]),
        Paragraph("Ghi chú kiểm chứng", st["section"]),
        Paragraph("Tài liệu mô phỏng này chỉ chứa các trường cần thiết cho bài toán xác minh thu nhập. Hệ thống không sử dụng nội dung để phê duyệt khoản vay hoặc tạo hợp đồng tín dụng.", st["body"]),
    ]
    doc(path, "Hợp đồng lao động - Nguyễn Thu Hà").build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    return path


def build_payslips(st: dict[str, ParagraphStyle]) -> Path:
    path = OUTPUT_DIR / "03_Bang_luong_6_thang_Nguyen_Thu_Ha.pdf"
    rows = []
    parser_lines = [f"Họ và tên: {CUSTOMER}", f"Công ty: {EMPLOYER}", f"Tiền tệ: {CURRENCY}"]
    for month in MONTHS:
        rows.append([month, money(CONTRACT_SALARY), "0 VND", "0 VND", money(CONTRACT_SALARY)])
        parser_lines.append(f"{month} | base: {CONTRACT_SALARY} | bonus: 0 | deduction: 0 | net: {CONTRACT_SALARY}")
    story = heading(st, "Tài liệu 03 - Payslip bundle", "Bảng lương tổng hợp 6 tháng", "Kỳ dữ liệu từ 01/2026 đến 06/2026 - đơn vị tiền tệ VND.")
    story += [
        info_grid(st, [
            ("Nhân viên", CUSTOMER),
            ("Đơn vị", EMPLOYER),
            ("Chức danh", "Chuyên viên phân tích dữ liệu"),
            ("Kỳ tổng hợp", "01/2026 - 06/2026"),
        ]),
        Paragraph("Chi tiết thu nhập theo kỳ", st["section"]),
        data_table(st, ["Kỳ", "Lương cơ bản", "Thưởng", "Khấu trừ", "Thực nhận"], rows, [24 * mm, 40 * mm, 30 * mm, 32 * mm, 42 * mm]),
        Spacer(1, 10),
        parser_block(st, parser_lines),
        Spacer(1, 8),
        Table([[Paragraph("Trạng thái đối soát", st["label"]), Paragraph("ĐỦ 6 KỲ - DỮ LIỆU ỔN ĐỊNH", st["value"]) ]], colWidths=[48 * mm, 120 * mm], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREEN), ("BOX", (0, 0), (-1, -1), 0.7, GREEN),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])),
    ]
    doc(path, "Bảng lương 6 tháng - Nguyễn Thu Hà").build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    return path


def build_statement(st: dict[str, ParagraphStyle]) -> Path:
    path = OUTPUT_DIR / "04_Sao_ke_ngan_hang_6_thang_Nguyen_Thu_Ha.pdf"
    rows = []
    parser_lines = [f"Khách hàng: {CUSTOMER}", f"Tiền tệ: {CURRENCY}"]
    for index, month in enumerate(MONTHS, 1):
        transaction_date = f"25/{index:02d}/2026"
        rows.append([transaction_date, "SALARY", EMPLOYER, money(CONTRACT_SALARY), CURRENCY])
        parser_lines.append(f"{month} | amount: {CONTRACT_SALARY} | source: {EMPLOYER} | description: SALARY")
    story = heading(st, "Tài liệu 04 - Bank statement", "Sao kê giao dịch nhận lương 6 tháng", "Bản sao kê giả lập chỉ hiển thị các giao dịch liên quan đến xác minh thu nhập.")
    story += [
        info_grid(st, [
            ("Chủ tài khoản", CUSTOMER),
            ("Số tài khoản hiển thị", "**** 8826"),
            ("Kỳ sao kê", "01/2026 - 06/2026"),
            ("Đơn vị tiền tệ", CURRENCY),
        ]),
        Paragraph("Giao dịch nhận lương", st["section"]),
        data_table(st, ["Ngày", "Mô tả", "Bên chuyển", "Số tiền ghi có", "Tiền tệ"], rows, [25 * mm, 27 * mm, 56 * mm, 39 * mm, 21 * mm]),
        Spacer(1, 10),
        parser_block(st, parser_lines),
        Spacer(1, 8),
        Paragraph("Ghi chú: Số tài khoản đã được che một phần. Tên đơn vị chuyển lương nhất quán với đơn vị công tác trên hợp đồng lao động.", st["small"]),
    ]
    doc(path, "Sao kê ngân hàng 6 tháng - Nguyễn Thu Hà").build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    return path


def generate() -> list[Path]:
    register_fonts()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    st = styles()
    return [build_application(st), build_contract(st), build_payslips(st), build_statement(st)]


if __name__ == "__main__":
    generated = generate()
    for item in generated:
        print(item)
