# consign_app/core_db/management/commands/load_mock_csv.py
import csv, json, re
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from consign_app.dataprev_mock.models import (
    MockINSSEspecie, MockINSSSituacao, MockINSSBeneficio,
    MockCLTTipoInscricao, MockCLTCbo, MockCLTRelacao,
)

DIGITS = re.compile(r"\D+")

def norm_digits(s: str) -> str:
    return DIGITS.sub("", s or "")

def parse_date(s: str):
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"invalid date: {s!r} (expected YYYY-MM-DD or DD/MM/YYYY)")

def parse_competencia(s: str) -> str:
    s = (s or "").strip()
    if not s:
        raise ValueError("empty 'competencia' (expected YYYY-MM)")
    # normalize 2025/09 -> 2025-09
    s = s.replace("/", "-")
    parts = s.split("-")
    if len(parts) != 2:
        raise ValueError(f"invalid 'competencia': {s!r} (expected YYYY-MM)")
    y, m = parts
    if len(y) != 4 or len(m) != 2:
        raise ValueError(f"invalid 'competencia' length: {s!r} (expected YYYY-MM)")
    int(y), int(m)  # validate numeric
    return f"{y}-{m}"

def read_csv(path: str):
    p = Path(path)
    if not p.exists():
        raise CommandError(f"file not found: {p}")
    with p.open(newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)

def load_inss_especies(path: str):
    created = updated = 0
    for row in read_csv(path):
        codigo = str(row.get("codigo") or row.get("CODIGO") or "").strip()
        descricao = (row.get("descricao") or row.get("DESCRICAO") or "").strip()
        if not codigo:
            continue
        _, is_created = MockINSSEspecie.objects.update_or_create(
            codigo=codigo, defaults={"descricao": descricao}
        )
        created += int(is_created)
        updated += int(not is_created)
    return created, updated

def load_inss_situacoes(path: str):
    created = updated = 0
    for row in read_csv(path):
        codigo = str(row.get("codigo") or row.get("CODIGO") or "").strip()
        descricao = (row.get("descricao") or row.get("DESCRICAO") or "").strip()
        if not codigo:
            continue
        _, is_created = MockINSSSituacao.objects.update_or_create(
            codigo=codigo, defaults={"descricao": descricao}
        )
        created += int(is_created)
        updated += int(not is_created)
    return created, updated

def load_inss_beneficios(path: str):
    created = updated = skipped = 0
    for row in read_csv(path):
        cpf = norm_digits(row.get("cpf") or row.get("CPF") or "")
        nb  = (row.get("numero_beneficio") or row.get("NB") or "").strip()
        cod_esp = (row.get("codigo_especie") or row.get("especie") or "").strip()
        cod_sit = (row.get("codigo_situacao") or row.get("situacao") or "").strip()
        data_inicio = parse_date(row.get("data_inicio") or row.get("DATA_INICIO") or "")

        if not (cpf and nb and cod_esp and cod_sit and data_inicio):
            skipped += 1
            continue

        desc_esp = (row.get("descricao_especie") or "").strip()
        desc_sit = (row.get("descricao_situacao") or "").strip()
        if desc_esp:
            MockINSSEspecie.objects.update_or_create(codigo=cod_esp, defaults={"descricao": desc_esp})
        if desc_sit:
            MockINSSSituacao.objects.update_or_create(codigo=cod_sit, defaults={"descricao": desc_sit})

        especie = MockINSSEspecie.objects.get(codigo=cod_esp)
        situacao = MockINSSSituacao.objects.get(codigo=cod_sit)

        _, is_created = MockINSSBeneficio.objects.update_or_create(
            numero_beneficio=nb,
            defaults=dict(cpf=cpf, especie=especie, situacao=situacao, data_inicio=data_inicio),
        )
        created += int(is_created)
        updated += int(not is_created)
    return created, updated, skipped

def load_clt_tipos_inscricao(path: str):
    created = updated = 0
    for row in read_csv(path):
        codigo = str(row.get("codigo") or "").strip()
        descricao = (row.get("descricao") or "").strip()
        if not codigo:
            continue
        _, is_created = MockCLTTipoInscricao.objects.update_or_create(
            codigo=codigo, defaults={"descricao": descricao}
        )
        created += int(is_created)
        updated += int(not is_created)
    return created, updated

def load_clt_cbos(path: str):
    created = updated = 0
    for row in read_csv(path):
        codigo = str(row.get("codigo") or "").strip()
        descricao = (row.get("descricao") or "").strip()
        if not codigo:
            continue
        _, is_created = MockCLTCbo.objects.update_or_create(
            codigo=codigo, defaults={"descricao": descricao}
        )
        created += int(is_created)
        updated += int(not is_created)
    return created, updated

def load_clt_relacoes(path: str):
    """
    Expected CSV headers:
    cpf, tipo_inscricao, numero_inscricao, data_admissao, data_encerramento, cbo_codigo, competencia, pendencias
    - pendencias: JSON (list of objects) or empty
    """
    created = updated = skipped = 0
    for row in read_csv(path):
        cpf = norm_digits(row.get("cpf") or "")
        tipo = (row.get("tipo_inscricao") or "").strip()
        num  = norm_digits(row.get("numero_inscricao") or "")
        adm  = parse_date(row.get("data_admissao") or "")
        fim  = parse_date(row.get("data_encerramento") or "")
        cbo  = (row.get("cbo_codigo") or "").strip()
        comp = parse_competencia(row.get("competencia") or "")

        if not (cpf and tipo and num and adm and cbo and comp):
            skipped += 1
            continue

        # upsert catalogs if present in CSV
        tipo_desc = (row.get("tipo_inscricao_descricao") or "").strip()
        cbo_desc  = (row.get("cbo_descricao") or "").strip()
        if tipo_desc:
            MockCLTTipoInscricao.objects.update_or_create(codigo=tipo, defaults={"descricao": tipo_desc})
        if cbo_desc:
            MockCLTCbo.objects.update_or_create(codigo=cbo, defaults={"descricao": cbo_desc})

        tipo_obj = MockCLTTipoInscricao.objects.get(codigo=tipo)
        cbo_obj  = MockCLTCbo.objects.get(codigo=cbo)

        pendencias_raw = (row.get("pendencias") or "").strip()
        if pendencias_raw:
            try:
                pendencias = json.loads(pendencias_raw)
            except json.JSONDecodeError as e:
                raise CommandError(f"invalid JSON for 'pendencias' (cpf={cpf}, employer={num}): {e}")
        else:
            pendencias = []

        _, is_created = MockCLTRelacao.objects.update_or_create(
            # suggested natural key
            cpf=cpf, numero_inscricao=num, data_admissao=adm,
            defaults=dict(
                tipo_inscricao=tipo_obj,
                data_encerramento=fim,
                cbo=cbo_obj,
                competencia=comp,
                pendencias=pendencias,
            ),
        )
        created += int(is_created)
        updated += int(not is_created)
    return created, updated, skipped

# ----------------- command -----------------
class Command(BaseCommand):
    help = "Load mock CSV files (INSS and CLT) into models."

    def add_arguments(self, parser):
        # INSS
        parser.add_argument("--inss-especies", help="CSV with columns: codigo, descricao")
        parser.add_argument("--inss-situacoes", help="CSV with columns: codigo, descricao")
        parser.add_argument(
            "--inss-beneficios",
            help="CSV with columns: cpf, numero_beneficio, codigo_especie, codigo_situacao, data_inicio [, descricao_especie, descricao_situacao]",
        )

        # CLT
        parser.add_argument("--clt-tipos", help="CSV with columns: codigo, descricao")
        parser.add_argument("--clt-cbos", help="CSV with columns: codigo, descricao")
        parser.add_argument(
            "--clt-relacoes",
            help="CSV with columns: cpf, tipo_inscricao, numero_inscricao, data_admissao, data_encerramento, cbo_codigo, competencia, pendencias (optional JSON list)",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        report = []

        if opts.get("inss_especies"):
            c, u = load_inss_especies(opts["inss_especies"]); report.append(f"INSS species   : +{c} / ~{u}")
        if opts.get("inss_situacoes"):
            c, u = load_inss_situacoes(opts["inss_situacoes"]); report.append(f"INSS situations: +{c} / ~{u}")
        if opts.get("inss_beneficios"):
            c, u, s = load_inss_beneficios(opts["inss_beneficios"]); report.append(f"INSS benefits  : +{c} / ~{u} / skipped={s}")

        if opts.get("clt_tipos"):
            c, u = load_clt_tipos_inscricao(opts["clt_tipos"]); report.append(f"CLT types      : +{c} / ~{u}")
        if opts.get("clt_cbos"):
            c, u = load_clt_cbos(opts["clt_cbos"]); report.append(f"CLT CBOs       : +{c} / ~{u}")
        if opts.get("clt_relacoes"):
            c, u, s = load_clt_relacoes(opts["clt_relacoes"]); report.append(f"CLT relations  : +{c} / ~{u} / skipped={s}")

        if not report:
            raise CommandError("No CSV provided. See --help.")
        self.stdout.write("\n".join(report))
