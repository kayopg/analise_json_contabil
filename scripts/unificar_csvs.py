import argparse
import csv
import os
from typing import List, Dict, Iterable, Tuple


def sniff_csv(path: str) -> Tuple[str, List[str]]:
    """Detecta delimitador e retorna os nomes de colunas do CSV."""
    # Tenta detectar delimitador via csv.Sniffer; fallback para ','
    delimiter = ','
    encoding_candidates = [
        'utf-8-sig',
        'utf-8',
        'latin-1',
    ]

    for enc in encoding_candidates:
        try:
            with open(path, 'r', encoding=enc, newline='') as f:
                sample = f.read(4096)
                if not sample:
                    return delimiter, []
                try:
                    dialect = csv.Sniffer().sniff(sample)
                    delimiter = dialect.delimiter
                except Exception:
                    delimiter = ','
                f.seek(0)
                reader = csv.reader(f, delimiter=delimiter)
                headers = next(reader, None) or []
                return delimiter, headers
        except UnicodeDecodeError:
            continue
    # Último recurso: abre como binário simples
    with open(path, 'r', encoding='latin-1', errors='replace', newline='') as f:
        sample = f.read(4096)
        try:
            dialect = csv.Sniffer().sniff(sample)
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ','
        f.seek(0)
        reader = csv.reader(f, delimiter=delimiter)
        headers = next(reader, None) or []
        return delimiter, headers


def iter_rows(path: str, delimiter: str, expected_headers: List[str]) -> Iterable[Dict[str, str]]:
    """Itera linhas como dicionários, preservando strings; garante chaves do conjunto esperado."""
    encoding_candidates = ['utf-8-sig', 'utf-8', 'latin-1']
    last_error = None
    for enc in encoding_candidates:
        try:
            with open(path, 'r', encoding=enc, newline='') as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                for row in reader:
                    # Normaliza para apenas as chaves esperadas (ou mantém todas?)
                    yield {k: (row.get(k, '') if row.get(k) is not None else '') for k in expected_headers}
            return
        except UnicodeDecodeError as e:
            last_error = e
            continue
    if last_error:
        raise last_error


def unify_csvs(inputs: List[str], output: str, add_origin: bool = True) -> None:
    # Coleta headers de cada arquivo e consolida como união
    file_info = []  # (path, delimiter, headers)
    all_headers = set()

    for p in inputs:
        if not os.path.isfile(p):
            raise FileNotFoundError(f"Arquivo não encontrado: {p}")
        delimiter, headers = sniff_csv(p)
        file_info.append((p, delimiter, headers))
        all_headers.update(headers)

    headers_order = list(all_headers)

    # Mantém ordem conhecida se presente
    preferred = ['matricula', 'nome', 'cpf', 'total']
    ordered = [h for h in preferred if h in all_headers]
    ordered += [h for h in headers_order if h not in preferred]
    headers_order = ordered

    if add_origin:
        headers_with_origin = headers_order + ['organograma']
    else:
        headers_with_origin = headers_order

    # Escreve saída
    os.makedirs(os.path.dirname(output) or '.', exist_ok=True)
    with open(output, 'w', encoding='utf-8', newline='') as out_f:
        writer = csv.DictWriter(out_f, fieldnames=headers_with_origin, delimiter=',')
        writer.writeheader()

        for p, delim, headers in file_info:
            base = os.path.basename(p)
            suffix = '_agrupado.csv'
            origem = base[:-len(suffix)] if base.lower().endswith(suffix) else base
            for row in iter_rows(p, delim, headers_order):
                if add_origin:
                    row['organograma'] = origem
                writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Unifica dados dos CSVs informados gerando uma saída única com '
            'união de colunas e coluna extra "organograma".'
        )
    )
    parser.add_argument(
        '-i', '--inputs', nargs='+', default=[
            '1802002_agrupado.csv',
            '11802004_agrupado.csv',
            '11802005_agrupado.csv',
        ], help='Arquivos CSV de entrada (padrão: três arquivos *_agrupado.csv do diretório atual)'
    )
    parser.add_argument(
        '-o', '--output', default='merged_agrupado.csv', help='Caminho do CSV de saída (padrão: merged_agrupado.csv)'
    )
    parser.add_argument(
        '--no-organograma', '--no-origem', dest='no_organograma', action='store_true',
        help='Não adiciona a coluna extra "organograma".'
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs = [os.path.abspath(p) for p in args.inputs]
    output = os.path.abspath(args.output)
    unify_csvs(inputs, output, add_origin=not args.no_organograma)
    print(f"Arquivo unificado gerado em: {output}")


if __name__ == '__main__':
    main()
