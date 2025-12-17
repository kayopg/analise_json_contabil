# Unificação de CSVs agrupados

Este script une os dados dos arquivos:
- 1802002_agrupado.csv
- 11802004_agrupado.csv
- 11802005_agrupado.csv

Ele detecta automaticamente o delimitador de cada CSV, aplica a união de colunas (preenchendo valores ausentes em branco) e adiciona a coluna `organograma` indicando de qual arquivo veio cada linha (removendo o sufixo `_agrupado.csv`).

## Uso

No Windows (PowerShell ou Prompt de Comando), a partir da pasta do projeto:

```powershell
python .\scripts\unificar_csvs.py -o .\merged_agrupado.csv
```

 Parâmetros principais:
 - `-i/--inputs`: lista de caminhos para arquivos de entrada (padrão: os três *_agrupado.csv do diretório atual)
 - `-o/--output`: caminho do arquivo CSV de saída (padrão: `merged_agrupado.csv`)
 - `--no-organograma` (alias: `--no-origem`): não adiciona a coluna extra `organograma`

Exemplos:

- Usando os arquivos padrão e gerando `merged_agrupado.csv`:
  ```powershell
  python .\scripts\unificar_csvs.py
  ```

- Especificando entradas e saída:
  ```powershell
  python .\scripts\unificar_csvs.py -i 1802002_agrupado.csv 11802004_agrupado.csv 11802005_agrupado.csv -o .\saida\todos_agrupados.csv
  ```

O arquivo de saída é gravado em UTF-8 com delimitador `,`.