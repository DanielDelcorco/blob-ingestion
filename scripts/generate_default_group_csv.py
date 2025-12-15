#!/usr/bin/env python3
"""Generate a large CSV for default_group tests/fixtures/default_group_large.csv
Header matches ingestion_config column_mapping.
Usage: ROWS=5000 python scripts/generate_default_group_csv.py
"""
import os

def main():
    rows = int(os.getenv("ROWS", "5000"))
    out = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures", "default_group_large.csv")
    out = os.path.abspath(out)
    header = "cod_grupo_limite_posicao,nome_grupo_limite_posicao,cod_cobranca_automatica,num_documento_integrante\n"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf8") as f:
        f.write(header)
        for i in range(1, rows + 1):
            group = (i % 500) + 1  # 500 distinct groups
            name = f"Default Group {group}"
            boolean = "S" if (i % 2 == 0) else "N"
            doc = f"doc-{i:07d}"
            f.write(f"{group},{name},{boolean},{doc}\n")
    print(f"Wrote {out} ({rows} rows)")

if __name__ == '__main__':
    main()
