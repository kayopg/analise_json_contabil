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
RE_VALOR = re.compile(r'^\s*valor:\s*"?(?P<v>[-+]?[0-9]+(?:[.,][0-9]+)?)"?\s*$', re.IGNORECASE)
RE_NUMERO_EVENTO = re.compile(r'^\s*numeroEvento:\s*"?(?P<v>[^"\r\n]+)"?\s*$', re.IGNORECASE)
RE_TIPO_EVENTO = re.compile(r'^\s*tipoEvento:\s*"?(?P<v>[^"\r\n]+)"?\s*$', re.IGNORECASE)
RE_FUNCIONARIOS_ARRAY = re.compile(r'^\s*funcionarios:\s*Array\b', re.IGNORECASE)
RE_NUMERO_ORGANOGRAMA = re.compile(r'^\s*numeroOrganograma:\s*"?(?P<v>[^"\r\n]+)"?\s*$', re.IGNORECASE)
RE_TIPO_PROVENTO = re.compile(r'^\s*tipoProvento:\s*"?(?P<v>[^"\r\n]+)"?\s*$', re.IGNORECASE)


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


# Pasta padrão de leitura (relativa ao root do projeto)
INPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "arquivos_leitura"))

# Lista de arquivos de entrada (pode ser configurada pelo usuário)
INPUT_FILES: list[str] = [
    "1802002.txt",
    "11802004.txt",
    "11802005.txt",
]  # Serão buscados dentro de INPUT_DIR quando caminho não for absoluto

# Listas de eventos a DESCONSIDERAR/EXCLUIR (numeroEvento)
# Deixe vazias para considerar TODOS os eventos daquele tipo.
EXCLUDE_PROVENTO_EVENTS: list[str] = [
    "295", "320", "340", "341", "342", "360", "590", "595", "860", "890",
    "960", "1015", "1115", "1405", "1545", "1755", "1765", "1955", "2000", "2001",
    "2003", "2004", "2006", "2008", "2009", "2012", "2013", "2014", "2015", "2016",
    "2017", "2018", "2019", "2020", "2021", "2023", "2024", "2025", "2026", "2028",
    "2034", "30109"
]  # Exclui estes PROVENTOS da geração do CSV
EXCLUDE_DESCONTO_EVENTS: list[str] = [
    "8340",
    "9005",
    "9015"
]  # Exclui estes DESCONTOS da geração do CSV


def parse_file(input_path: str) -> Tuple[Dict[str, Decimal], Dict[str, Tuple[str, str]], list[Tuple[str, str, str, str, str, Decimal, str]]]:
    """Processa um arquivo .txt e retorna (totals, meta, details).

    details: lista de tuplas (matricula, nome, cpf, numeroEvento, tipoEvento, valorEvento, numeroOrganograma)
    """
    totals: Dict[str, Decimal] = {}
    meta: Dict[str, Tuple[str, str]] = {}
    details: list[Tuple[str, str, str, str, str, Decimal, str]] = []

    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        lines = [ln.rstrip("\n") for ln in f]

    current_matricula: Optional[str] = None
    current_nome: str = ""
    current_cpf: str = ""
    current_event_type: Optional[str] = None  # 'PROVENTO' ou 'DESCONTO'
    current_event_number: Optional[str] = None
    within_funcionarios: bool = False
    current_numero_organograma: Optional[str] = None

    # Buffer do evento corrente (quando tipo/numero aparecem DEPOIS do array)
    pending_event_contribs: list[Tuple[str, str, str, Decimal]] = []
    pending_event_number: Optional[str] = None
    pending_event_type: Optional[str] = None
    pending_event_organograma: Optional[str] = None

    for ln in lines:
        # helper: verifica se o evento NÃO está em listas de exclusão
        def _allowed_event(num: Optional[str], typ: Optional[str]) -> bool:
            ptype = (typ or "").upper()
            if ptype == "PROVENTO":
                # se lista vazia, permite todos; senão, permite apenas se não estiver na lista
                return (not EXCLUDE_PROVENTO_EVENTS) or (num not in EXCLUDE_PROVENTO_EVENTS)
            if ptype == "DESCONTO":
                return (not EXCLUDE_DESCONTO_EVENTS) or (num not in EXCLUDE_DESCONTO_EVENTS)
            return False

        m_ne = RE_NUMERO_EVENTO.match(ln)
        if m_ne:
            current_event_number = m_ne.group("v").strip()
            pending_event_number = current_event_number
            within_funcionarios = False
            if pending_event_type and pending_event_contribs:
                ptype = pending_event_type or ""
                sign = Decimal("1") if ptype == "PROVENTO" else Decimal("-1")
                if _allowed_event(pending_event_number, pending_event_type):
                    for (mat, nome, cpf, val) in pending_event_contribs:
                        applied = (val * sign)
                        totals[mat] = totals.get(mat, Decimal("0")) + applied
                        details.append((mat, nome, cpf, pending_event_number or "", ptype, applied, pending_event_organograma or ""))
                pending_event_contribs.clear()
                pending_event_number = None
                pending_event_type = None
                pending_event_organograma = None
            continue

        m_no = RE_NUMERO_ORGANOGRAMA.match(ln)
        if m_no:
            current_numero_organograma = m_no.group("v").strip()
            continue

        m = RE_TIPO_EVENTO.match(ln) or RE_TIPO_PROVENTO.match(ln)
        if m:
            current_event_type = m.group("v").strip().upper()
            pending_event_type = current_event_type
            within_funcionarios = False
            if pending_event_number and pending_event_contribs:
                ptype = pending_event_type or ""
                sign = Decimal("1") if ptype == "PROVENTO" else Decimal("-1")
                if _allowed_event(pending_event_number, pending_event_type):
                    for (mat, nome, cpf, val) in pending_event_contribs:
                        applied = (val * sign)
                        totals[mat] = totals.get(mat, Decimal("0")) + applied
                        details.append((mat, nome, cpf, pending_event_number or "", ptype, applied, pending_event_organograma or ""))
                pending_event_contribs.clear()
                pending_event_number = None
                pending_event_type = None
                pending_event_organograma = None
            continue

        if RE_FUNCIONARIOS_ARRAY.match(ln):
            within_funcionarios = True
            pending_event_contribs.clear()
            pending_event_number = None
            pending_event_type = None
            pending_event_organograma = current_numero_organograma

        m = RE_MATRICULA.match(ln)
        if m:
            current_matricula = m.group("v").strip()
            mat = current_matricula
            if within_funcionarios and mat:
                totals.setdefault(mat, Decimal("0"))
            if current_matricula and (current_nome or current_cpf):
                meta[current_matricula] = (current_nome, current_cpf)
            continue

        m = RE_NOME.match(ln)
        if m:
            current_nome = m.group("v").strip()
            if current_matricula:
                meta[current_matricula] = (current_nome, current_cpf)
            continue

        m = RE_CPF.match(ln)
        if m:
            current_cpf = m.group("v").strip()
            if current_matricula:
                meta[current_matricula] = (current_nome, current_cpf)
            continue

        if within_funcionarios and current_matricula:
            m_val = RE_VALOR.match(ln)
            if m_val:
                val = parse_decimal(m_val.group("v"))
                if val is not None:
                    nome, cpf = meta.get(current_matricula, (current_nome, current_cpf))
                    pending_event_contribs.append((current_matricula, nome, cpf, val))
                continue

    return totals, meta, details


def main(argv: list[str]) -> int:
    # Determina lista de arquivos de entrada
    if len(argv) >= 2:
        input_files = argv[1:]
    elif INPUT_FILES:
        input_files = INPUT_FILES
    else:
        input_files = []

    q = Decimal("0.01")

    # Helpers de ordenação
    def _mat_key(mat: str) -> Tuple[int, str]:
        try:
            return (int(mat), "")
        except Exception:
            return (sys.maxsize, mat)

    def _org_label(input_path: str) -> str:
        base = os.path.splitext(os.path.basename(input_path))[0]
        if base.endswith("_agrupado"):
            base = base[: -len("_agrupado")]
        return base

    def _orgnum_key(orgnum: str) -> Tuple[int, str]:
        try:
            return (int(orgnum), "")
        except Exception:
            return (sys.maxsize, orgnum)

    def _event_key(t: str) -> int:
        tt = (t or "").upper()
        if tt == "PROVENTO":
            return 0
        if tt == "DESCONTO":
            return 1
        return 99

    # Resolve caminhos relativos para dentro de INPUT_DIR
    def _resolve_inputs(files: list[str]) -> list[str]:
        result: list[str] = []
        for p in files:
            if os.path.isabs(p):
                result.append(p)
            else:
                result.append(os.path.join(INPUT_DIR, p))
        return result

    # Unifica detalhes de todos os arquivos e acumula agregados para saída única
    unified_details: list[Tuple[str, str, str, str, str, str, Decimal, str]] = []
    unified_aggregates: list[Tuple[str, str, str, Decimal, str]] = []

    # Converte nomes para caminhos absolutos dentro de INPUT_DIR, quando necessário
    input_files = _resolve_inputs(input_files)

    for input_path in input_files:
        totals, meta, details = parse_file(input_path)
        organograma = _org_label(input_path)
        # acumula agregados para escrita única ao final
        for matricula in totals.keys():
            nome, cpf = meta.get(matricula, ("", ""))
            total = totals[matricula].quantize(q, rounding=ROUND_HALF_UP)
            unified_aggregates.append((matricula, nome, cpf, total, organograma))

        # agrega no detalhe unificado
        for (mat, nome, cpf, nevento, tevento, applied, orgnum) in details:
            unified_details.append((orgnum, mat, nome, cpf, nevento, tevento, applied, organograma))

    output_path = "detalhe_unificado.csv"

    # Se não há arquivos para leitura, escreve mensagem informativa no arquivo final
    if not input_files:
        with open(output_path, "w", encoding="utf-8", newline="") as csvfile:
            w = csv.writer(csvfile)
            w.writerow(["mensagem"])
            w.writerow(["Nenhum arquivo de leitura informado (use argumentos ou preencha INPUT_FILES)."])
        return 0

    # Ordena por numeroOrganograma, matrícula e tipoEvento
    unified_details.sort(key=lambda r: (_orgnum_key(r[0]), _mat_key(r[1]), _event_key(r[5])))

    # Escreve único arquivo detalhado unificado com coluna "organograma"
    with open(output_path, "w", encoding="utf-8", newline="") as csvfile:
        w = csv.writer(csvfile)
        w.writerow(["numeroOrganograma", "matricula", "nome", "cpf", "numeroEvento", "tipoEvento", "valorEvento", "organograma"])
        for orgnum, mat, nome, cpf, nevento, tevento, applied, org in unified_details:
            w.writerow([orgnum, mat, nome, cpf, nevento, tevento, f"{applied.quantize(q, rounding=ROUND_HALF_UP)}", org])

    # Escreve único arquivo agregado por matrícula, com coluna "organograma"
    output_agg_all = "valores_agrupados_por_matricula.csv"
    unified_aggregates.sort(key=lambda r: (_org_label(r[4]), _mat_key(r[0])))
    with open(output_agg_all, "w", encoding="utf-8", newline="") as csvfile:
        w = csv.writer(csvfile)
        w.writerow(["matricula", "nome", "cpf", "total", "organograma"])
        for matricula, nome, cpf, total, org in unified_aggregates:
            w.writerow([matricula, nome, cpf, f"{total}", org])

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
