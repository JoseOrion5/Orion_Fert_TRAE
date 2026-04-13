import pandas as pd
import sys

files = [
    (r"T:\GitHub\Nova pasta\0.novo sabado 1737h\DO TRAE- Continuação Antigravity - Trabalho 31.03.26 - Copia - Copia\COMPLETAO\2.2 Claude-fertilizantes_precos_kg.xlsx", 0),
    (r"T:\GitHub\Nova pasta\0.novo sabado 1737h\DO TRAE- Continuação Antigravity - Trabalho 31.03.26 - Copia - Copia\COMPLETAO\2.2-Fertilizantes_solidos_BR_AZ_com_precos_alibaba.xlsx", 1),
    (r"T:\GitHub\Nova pasta\0.novo sabado 1737h\DO TRAE- Continuação Antigravity - Trabalho 31.03.26 - Copia - Copia\COMPLETAO\2-BASE_UNICA_COM_PRECOS_E_MAX_INFO_COM_FONTES.xlsx", 1)
]

for f,h in files:
    try:
        print(f"--- File: {f} ---")
        df = pd.read_excel(f, header=h)
        print("Columns:", [c.encode('ascii', 'ignore').decode() if isinstance(c, str) else c for c in df.columns])
        # print("Sample:")
        # print(df.head(2).applymap(lambda x: str(x).encode('ascii', 'ignore').decode() if isinstance(x, str) else x).to_dict('records'))
    except Exception as e:
        print(f"Error reading {f}: {e}")
