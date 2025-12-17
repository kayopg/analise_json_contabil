#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera CSV agrupado a partir do arquivo 1802002.txt.

O arquivo 1802002.txt deve conter, por linha, um JSON (ou trecho de JSON)
representando um registro de funcionário com os campos:
  - matricula
  - nome
  - cpf
  - valor

Este script:
  1) lê 1802002.txt em UTF-8 (com tolerância a erros)
  2) tenta extrair os campos mesmo com linhas malformadas
  3) soma o campo valor por matrícula
  4) grava 1802002_agrupado.csv ordenado por matrícula

Saída:
  matricula,total

Requisitos: Python 3.8+
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, Optional, Tuple


# Regexes de fallback para linhas que não são JSON válido
_RE_MATRICULA = re.compile(r"\"matricula\"\s*:\s*(\"([^\"]*)\"|([^,}\]]+))", re.IGNORECASE)
_RE_NOME = re.compile(r"\"nome\"\s*:\s*(\"([^\"]*)\"|([^,}\]]+))", re.IGNORECASE)
_RE_CPF = re.compile(r"\"cpf\"\s*:\s*(\"([^\"]*)\"|([^,}\]]+))", re.IGNORECASE)
_RE_VALOR = re.compile(r"\"valor\"\s*:\s*(\"([^\"]*)\"|([^,}\]]+))", re.IGNORECASE)


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        return s[1:-1]
    return s


def parse_valor(raw: Any) -> Optional[Decimal]:
    """Converte valor para Decimal.

    Aceita número como int/float/Decimal ou string (com ou sem aspas no arquivo).
    Tenta lidar com separadores de milhar e decimal comuns.

    Regras:
      - usa ponto como separador decimal na saída
      - tolera entradas como "1234.56", "1.234,56", "1234,56", "1,234.56"
      - em caso de ambiguidade, aplica heurística simples
    """
    if raw is None:
        return None

    if isinstance(raw, (int, Decimal)):
        return Decimal(raw)

    if isinstance(raw, float):
        # Evita problemas binários
        return Decimal(str(raw))

    s = str(raw).strip()
    s = _strip_quotes(s)
    s = s.strip()
    if not s:
        return None

    # Remove espaços
    s = s.replace(" ", "")

    # Heurística para vírgula/ponto
    # Se tem '.' e ',' decide qual é decimal pelo último separador.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            # Formato tipo 1.234,56
            s = s.replace(".", "")
            s = s.replace(",", ".")
        else:
            # Formato tipo 1,234.56
            s = s.replace(",", "")
    elif "," in s:
        # Se só vírgula, assume decimal
        s = s.replace(".", "")  # caso raro de milhar com ponto e decimal com vírgula ausente
        s = s.replace(",", ".")
    else:
        # Só ponto ou nenhum separador
        pass

    # Remove quaisquer caracteres não numéricos comuns (mantém sinal e ponto)
    s = re.sub(r"[^0-9+\-\.]", "", s)
    if s in {"", ".", "+", "-", "+.", "-."}:
        return None

    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def extract_fields_from_json(obj: Any) -> Optional[Tuple[str, str, str, Any]]:
    """Extrai (matricula, nome, cpf, valor) de um dict JSON.

    Retorna None se não conseguir matrícula.
    """
    if not isinstance(obj, dict):
        return None

    def get_key(d: Dict[str, Any], key: str) -> Any:
        # tenta chave exata e variações comuns
        if key in d:
            return d[key]
        # algumas bases usam caixa diferente
        for k, v in d.items():
            if isinstance(k, str) and k.lower() == key.lower():
                return v
        return None

    matricula = get_key(obj, "matricula")
    nome = get_key(obj, "nome")
    cpf = get_key(obj, "cpf")
    valor = get_key(obj, "valor")

    if matricula is None:
        return None

    matricula_s = _strip_quotes(str(matricula)).strip()
    nome_s = "" if nome is None else _strip_quotes(str(nome)).strip()
    cpf_s = "" if cpf is None else _strip_quotes(str(cpf)).strip()

    return (matricula_s, nome_s, cpf_s, valor)


def extract_fields_fallback(line: str) -> Optional[Tuple[str, str, str, Any]]:
    """Fallback com regex para linhas malformadas (não-JSON)."""

    def mval(rx: re.Pattern[str]) -> Optional[str]:
        m = rx.search(line)
        if not m:
            return None
        # grupo 2: conteúdo entre aspas; grupo 3: sem aspas
        v = m.group(2) if m.group(2) is not None else m.group(3)
        return _strip_quotes(v).strip() if v is not None else None

    matricula = mval(_RE_MATRICULA)
    if not matricula:
        return None

    nome = mval(_RE_NOME) or ""
    cpf = mval(_RE_CPF) or ""
    valor = mval(_RE_VALOR)

    return (matricula, nome, cpf, valor)


def iter_funcionarios(path: str) -> Iterable[Tuple[str, str, str, Any]]:
    """Itera por entradas de funcionário no arquivo.

    Cada linha é tratada como um JSON independente.
    Linhas vazias são ignoradas.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            # Tenta JSON primeiro
            try:
                obj = json.loads(line)
                extracted = extract_fields_from_json(obj)
                if extracted is not None:
                    yield extracted
                    continue
            except Exception:
                pass

            # Fallback regex
            extracted = extract_fields_fallback(line)
            if extracted is not None:
                yield extracted
            else:
                # tolera linha malformada
                continue


def main(argv: list[str]) -> int:
    input_path = "1802002.txt"
    output_path = "1802002_agrupado.csv"

    if len(argv) >= 2:
        input_path = argv[1]
    if len(argv) >= 3:
        output_path = argv[2]

    totals: Dict[str, Decimal] = {}

    for matricula, _nome, _cpf, valor_raw in iter_funcionarios(input_path):
        valor = parse_valor(valor_raw)
        if valor is None:
            continue
        totals[matricula] = totals.get(matricula, Decimal("0")) + valor

    # Ordena por matrícula (string). Se quiser numérico, manter zeros à esquerda pode ser importante.
    items = sorted(totals.items(), key=lambda kv: kv[0])

    # Garante diretório do output quando informado com caminho
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    q = Decimal("0.01")
    with open(output_path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["matricula", "total"])
        for matricula, total in items:
            total_fmt = str(total.quantize(q, rounding=ROUND_HALF_UP))
            writer.writerow([matricula, total_fmt])

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
