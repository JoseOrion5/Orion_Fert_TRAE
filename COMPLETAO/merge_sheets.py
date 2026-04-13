import pandas as pd
import numpy as np
import difflib

# Paths
file1_path = r"COMPLETAO\BACKUP\2.2 Claude-fertilizantes_precos_kg.xlsx"
file2_path = r"COMPLETAO\BACKUP\2.2-Fertilizantes_solidos_BR_AZ_com_precos_alibaba.xlsx"
base_path = r"COMPLETAO\2-BASE_UNICA_COM_PRECOS_E_MAX_INFO_COM_FONTES.xlsx"
output_path = r"COMPLETAO\DATABASE_MESTRE_ORION.xlsx"

# Load DataFrames
df1 = pd.read_excel(file1_path, header=0)
df2 = pd.read_excel(file2_path, header=1)
df_base = pd.read_excel(base_path, header=1)

# Rename problematic header if needed, Base has header on row 1 (0-indexed 1)
# Usually first row is title, second row is header.

def clean_name(name):
    if pd.isna(name): return ""
    return str(name).strip().lower()

def safe_float(val):
    if pd.isna(val): return np.nan
    if isinstance(val, (int, float)): return float(val)
    # clean string
    s = str(val).replace('US$', '').replace('U$', '').replace('$', '').replace('BRL', '').replace('R$', '').strip()
    s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return np.nan

# Extract prices from df1
prices_dict = {} # key: clean_name, value: list of prices
for _, row in df1.iterrows():
    name = row.get("Fertilizante")
    # find the price column. It's 'Preço Médio (U$/kg)' or similar
    price_col = [c for c in df1.columns if 'U$' in c and 'M' in c and 'dio' in c]
    if not price_col:
        price_col = [c for c in df1.columns if 'Pre' in c]
    if price_col:
        price = safe_float(row[price_col[0]])
        if not np.isnan(price):
            cn = clean_name(name)
            if cn not in prices_dict: prices_dict[cn] = []
            prices_dict[cn].append(price)

# Extract prices from df2
for _, row in df2.iterrows():
    name_col = [c for c in df2.columns if 'Nome' in c]
    if name_col:
        name = row[name_col[0]]
        price_col = [c for c in df2.columns if 'USD' in c or 'Preço' in c]
        if price_col:
            price = safe_float(row[price_col[0]])
            if not np.isnan(price):
                cn = clean_name(name)
                if cn not in prices_dict: prices_dict[cn] = []
                prices_dict[cn].append(price)

# Update the Base DataFrame
# Base price col is "Estimativa de Preço Médio (R$)"
price_col_base = [c for c in df_base.columns if 'Estimativa de Pre' in c]
base_price_col_name = price_col_base[0] if price_col_base else 'Estimativa de Preço Médio'

# Let's rename the currency column to U$
df_base = df_base.rename(columns={base_price_col_name: 'Estimativa de Preço Médio (U$)'})

for idx, row in df_base.iterrows():
    name = clean_name(row.get('Nome'))
    # Convert existing BRL price to USD (divide by 5 for est) if there's no match?
    # Or just leave it. Let's find matches.
    matches = difflib.get_close_matches(name, prices_dict.keys(), n=1, cutoff=0.8)
    
    current_val = safe_float(row.get('Estimativa de Preço Médio (U$)'))
    all_prices = []
    
    if "brl" in str(row.get("BRL", "")).lower() or "brl" in str(row.get("Unnamed: 21", "")).lower() or "brl" in str(row.get("Moeda", "")).lower():
         if not np.isnan(current_val):
             current_val = current_val / 5.5 # Rough conversion to USD
             
    if not np.isnan(current_val):
        all_prices.append(current_val)
        
    if matches:
        all_prices.extend(prices_dict[matches[0]])
        
    if all_prices:
        avg_price = sum(all_prices) / len(all_prices)
        df_base.at[idx, 'Estimativa de Preço Médio (U$)'] = round(avg_price, 3)
        # Update currency indicator
        # find currency col 
        curr_cols = [c for c in df_base.columns if df_base[c].astype(str).str.contains('BRL').any() or 'BRL' in str(c) or 'Moeda' in str(c)]
        if curr_cols:
            df_base.at[idx, curr_cols[0]] = 'USD'
        elif 'BRL' in df_base.columns:
            df_base.at[idx, 'BRL'] = 'USD'

# Now append any missing items from File 1 and File 2
base_names = [clean_name(x) for x in df_base['Nome'].dropna().tolist()]

new_rows = []

for _, row in df1.iterrows():
    name = row.get("Fertilizante")
    cn = clean_name(name)
    if cn and not difflib.get_close_matches(cn, base_names, n=1, cutoff=0.8):
        # We need to add it
        price_col = [c for c in df1.columns if 'U$' in c and 'io' in c]
        if not price_col: price_col = [c for c in df1.columns if 'Pre' in c]
        price = safe_float(row[price_col[0]]) if price_col else np.nan
        new_row = {
            'Tipo': 'Fertilizante',
            'Nome': name,
            'Categoria': row.get('Categoria'),
            'Teor(es) / Garantia (%)': row.get('Garantia Nutricional'),
            'Estimativa de Preço Médio (U$)': price,
            'BRL': 'USD' if not np.isnan(price) else '' # BRL/USD column
        }
        new_rows.append(new_row)
        base_names.append(cn)

for _, row in df2.iterrows():
    name_col = [c for c in df2.columns if 'Nome' in c]
    if name_col:
        name = row[name_col[0]]
        cn = clean_name(name)
        if cn and not difflib.get_close_matches(cn, base_names, n=1, cutoff=0.8):
            price_col = [c for c in df2.columns if 'USD' in c or 'Preço' in c]
            price = safe_float(row[price_col[0]]) if price_col else np.nan
            new_row = {
                'Tipo': 'Fertilizante',
                'Nome': name,
                'Categoria': row.get('Categoria'),
                'Teor(es) / Garantia (%)': row.get('Garantia típica'),
                'Natureza física': row.get('Forma'),
                'Padrão Ouro / Observações': row.get('Uso no Brasil (observações)'),
                'Estimativa de Preço Médio (U$)': price,
                'BRL': 'USD' if not np.isnan(price) else '',
                'Fonte/Fornecedor (preço)': row.get('Fonte (Alibaba)')
            }
            new_rows.append(new_row)
            base_names.append(cn)

if new_rows:
    df_new = pd.DataFrame(new_rows)
    df_base = pd.concat([df_base, df_new], ignore_index=True)

# Save the updated base
# Recreate the first row title for styling maybe?
# Openpyxl is better for keeping format, but the user asked for a fluid organized integration.
# We will just save with pandas.
# Let's save and then we can check.
df_base.to_excel(output_path, index=False)
print("Merge complete. File saved to: ", output_path)
