import pandas as pd
from pathlib import Path

BASE_UNICA_FILE = Path("COMPLETAO/DATABASE_MESTRE_ORION.xlsx")
if BASE_UNICA_FILE.exists():
    df = pd.read_excel(BASE_UNICA_FILE, sheet_name="Insumos")
    print("Columns:", df.columns.tolist())
    print("\nSample (first 5 rows):")
    print(df.head(5))
else:
    print(f"File not found: {BASE_UNICA_FILE}")
