"""Anonymized bank-export workbooks, generated in-memory.

Mirrors the real layouts in backend/bank-exports-examples/ (gitignored, PII)
without shipping any personal data: same preamble shape, header rows, cell
types (float amounts, DD/MM/YYYY string dates).
"""

from io import BytesIO
from typing import Any

import xlwt
from openpyxl import Workbook

BBVA_HEADER = [
    None,
    "F.Valor",
    "Fecha",
    "Concepto",
    "Movimiento",
    "Importe",
    "Divisa",
    "Disponible",
    "Divisa",
    "Observaciones",
]

# (f_valor, fecha, concepto, movimiento, importe, disponible, observaciones)
BBVA_ROWS: list[tuple[str, str, str, str, float, float, str]] = [
    ("10/06/2026", "10/06/2026", "Supermercado genérico", "Pago con tarjeta", -23.27, 594.21, "COMPRA 1111"),
    ("08/06/2026", "10/06/2026", "Suscripción música", "Pago con tarjeta", -9.99, 617.48, "SUSCRIPCION"),
    ("09/06/2026", "09/06/2026", "Bizum", "Enviado: regalo", -7.05, 627.47, "ENVIADO"),
    # Same day, same description and amount, different balance: two real coffees.
    ("09/06/2026", "09/06/2026", "Cafetería central", "Pago con tarjeta", -1.50, 634.52, "CAFE"),
    ("09/06/2026", "09/06/2026", "Cafetería central", "Pago con tarjeta", -1.50, 636.02, "CAFE"),
    ("02/06/2026", "02/06/2026", "Abono de nómina", "Empresa ejemplo sl", 881.29, 637.52, "NOMINA"),
]

SABADELL_PREAMBLE = [
    ["Consulta de movimientos"],
    ["11/06/2026 0:02:46"],
    [],
    ["Cuenta: ", "ES00 0000 0000 0000 0000 0000"],
    ["Divisa: ", "EUR"],
    ["Titular:", "NOMBRE*EJEMPLO"],
    ["Selección:", "Desde 01/04/2026 hasta 10/06/2026"],
    [],
]

SABADELL_HEADER = ["F. Operativa", "Concepto", "F. Valor", "Importe", "Saldo", "Referencia 1", "Referencia 2"]

# (f_operativa, concepto, f_valor, importe, saldo, ref1, ref2)
SABADELL_ROWS: list[tuple[str, str, str, float, float, str, str]] = [
    ("09/06/2026", "COMPRA TARJ. 0000XXXXXXXX0000 Tienda online", "12/06/2026", -24.54, 33.83, "", "0000__0000"),
    ("09/06/2026", "COMISIÓN DIVISA NO EURO", "12/06/2026", -0.86, 32.97, "", "0000__0000"),
    ("05/06/2026", "TRANSFERENCIA RECIBIDA", "05/06/2026", 150.00, 208.37, "", ""),
    ("02/06/2026", "RECIBO LUZ COMPAÑÍA", "02/06/2026", -58.37, 58.37, "", ""),
]


def bbva_xlsx(rows: list[tuple[Any, ...]] | None = None) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Informe BBVA"
    sheet.append([])
    sheet.append([None, None, None, "Últimos movimientos"])
    sheet.append([None, None, None, "Fecha de generación del informe: 10/06/2026"])
    sheet.append([])
    sheet.append(BBVA_HEADER)
    for f_valor, fecha, concepto, movimiento, importe, disponible, obs in rows or BBVA_ROWS:
        sheet.append([None, f_valor, fecha, concepto, movimiento, importe, "EUR", disponible, "EUR", obs])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def sabadell_xls(rows: list[tuple[Any, ...]] | None = None) -> bytes:
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Hoja1")
    for r, values in enumerate(SABADELL_PREAMBLE):
        for c, value in enumerate(values):
            sheet.write(r, c, value)
    header_row = len(SABADELL_PREAMBLE)
    for c, name in enumerate(SABADELL_HEADER):
        sheet.write(header_row, c, name)
    for r, values in enumerate(rows or SABADELL_ROWS, start=header_row + 1):
        for c, value in enumerate(values):
            sheet.write(r, c, value)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
