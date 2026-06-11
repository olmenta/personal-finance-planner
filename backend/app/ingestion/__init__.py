"""Transaction ingestion port and bank adapters (project-definition §6.3).

Every external source (bank exports today; Open Banking, WhatsApp, OCR later)
implements TransactionSource and feeds the same import pipeline.
"""

from .base import NormalizedTransaction, StatementFormatError, TransactionSource
from .bbva import BBVAXlsxAdapter
from .custom_csv import CustomCsvAdapter
from .sabadell import SabadellXlsAdapter

ADAPTERS: dict[str, TransactionSource] = {
    "bbva": BBVAXlsxAdapter(),
    "sabadell": SabadellXlsAdapter(),
    "custom": CustomCsvAdapter(),
}

__all__ = [
    "ADAPTERS",
    "BBVAXlsxAdapter",
    "CustomCsvAdapter",
    "NormalizedTransaction",
    "SabadellXlsAdapter",
    "StatementFormatError",
    "TransactionSource",
]
