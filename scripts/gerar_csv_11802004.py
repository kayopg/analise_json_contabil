#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import os
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, Optional, Tuple


RE_MATRICULA = re.compile(r'^\s*matricula:\s*"?(?P<v>[^"\r\n]+)"?\s*$', re.IGNORECASE)
RE_NOME = re.compile(r'^\s*nome:\s*"?(?P<v>[^"\r\n]+)"?\s*$', re.IGNORECASE)
RE_CPF = re.compile(r'^\s*cpf:\s*"?(?P<v>[^"\r\n]+)"?\s*$', re.IGNORECASE)
RE_VALOR = re.compile(r'^\s*valor:\s*(?P<v>[-+]?[0-9]+(?:[.,][0-9]+)?)\s*$', re.IGNORECASE)


def parse_decimal(s: str) -> Optional[Decimal]:
    s = s.strip().replace(" ", "")
    if not s:
        return None

    # Suporta "1234.56" e "1234,56"
    if "," in s and "." in s:
        # decide pelo último separador como decimal
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")

    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def main(argv: list[str]) -> int:
    input_path = "11802004.txt"
    output_path = "11802004_agrupado.csv"

    if len(argv) >= 2:
        input_path = argv[1]
    if len(argv) >= 3:
        output_path = argv[2]

    totals: Dict[str, Decimal] = {}
    meta: Dict[str, Tuple[str, str]] = {}  # matricula -> (nome, cpf)

    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        lines = [ln.rstrip("\n") for ln in f]

    i = 0
    while i < len(lines):
        m_mat = RE_MATRICULA.match(lines[i])
        if not m_mat:
            i += 1
            continue

        matricula = m_mat.group("v").strip()

        # precisa ter mais 3 linhas
        if i + 3 >= len(lines):
            break

        m_nome = RE_NOME.match(lines[i + 1])
        m_cpf = RE_CPF.match(lines[i + 2])
        m_val = RE_VALOR.match(lines[i + 3])

        if not (m_nome and m_cpf and m_val):
            # não é um bloco válido, anda 1 linha e tenta de novo
            i += 1
            continue

        nome = m_nome.group("v").strip()
        cpf = m_cpf.group("v").strip()
        valor = parse_decimal(m_val.group("v"))

        if valor is not None:
            totals[matricula] = totals.get(matricula, Decimal("0")) + valor
            meta.setdefault(matricula, (nome, cpf))

        i += 4  # avança para o próximo possível funcionário

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    q = Decimal("0.01")
    with open(output_path, "w", encoding="utf-8", newline="") as csvfile:
        w = csv.writer(csvfile)
        w.writerow(["matricula", "nome", "cpf", "total"])
        for matricula in sorted(totals.keys()):
            nome, cpf = meta.get(matricula, ("", ""))
            total = totals[matricula].quantize(q, rounding=ROUND_HALF_UP)
            w.writerow([matricula, nome, cpf, f"{total}"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))