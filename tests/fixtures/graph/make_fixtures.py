"""Regenerate the binary graph fixtures (xlsx/pdf)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook


ROOT = Path(__file__).resolve().parent


def make_excel() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(["公司", "核心产品", "原材料"])
    sheet.append(["贵州茅台酒股份有限公司", "茅台酒", "高粱"])
    sheet.append(["宁德时代新能源科技股份有限公司", "动力电池", "碳酸锂"])
    sheet.append(["赣锋锂业股份有限公司", "碳酸锂", "锂辉石"])
    workbook.save(ROOT / "excel" / "supply-chain.xlsx")


def make_pdf() -> None:
    content = (
        "BT /F1 12 Tf 72 720 Td (Moutai produces Moutai liquor.) Tj "
        "0 -20 Td (CATL purchases lithium carbonate from Ganfeng.) Tj "
        "0 -20 Td (Wuliangye competes with Moutai.) Tj ET"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content.encode('ascii'))} >>\nstream\n{content}\nendstream".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    raw = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(raw))
        raw += f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_position = len(raw)
    raw += b"xref\n0 " + str(len(objects) + 1).encode("ascii") + b"\n"
    raw += b"0000000000 65535 f \n"
    for offset in offsets:
        raw += f"{offset:010d} 00000 n \n".encode("ascii")
    raw += b"trailer\n<< /Size " + str(len(objects) + 1).encode("ascii") + b" /Root 1 0 R >>\n"
    raw += b"startxref\n" + str(xref_position).encode("ascii") + b"\n%%EOF\n"
    (ROOT / "pdf" / "supply-chain.pdf").write_bytes(bytes(raw))


def main() -> None:
    (ROOT / "excel").mkdir(parents=True, exist_ok=True)
    (ROOT / "pdf").mkdir(parents=True, exist_ok=True)
    make_excel()
    make_pdf()


if __name__ == "__main__":
    main()
