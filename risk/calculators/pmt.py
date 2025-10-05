# -*- coding: utf-8 -*-
"""
Tabela Price (juros compostos mensais) + utilitários.
- pmt_price: parcela fixa
- eff_annual_from_monthly: conversão i_mensal -> CET anual (sem tarifas)
- amortization_schedule: cronograma (opcional, para auditoria)

Convencões:
- rate_monthly: taxa mensal em decimal (ex.: 0.025 = 2,5% a.m.)
- n_months: prazo em meses (int > 0)
- pv: principal (valor presente) > 0
"""

from typing import List, Dict

def pmt_price(rate_monthly: float, n_months: int, pv: float) -> float:
    r = float(rate_monthly)
    n = int(n_months)
    pv = float(pv)
    if n <= 0:
        raise ValueError("n_months deve ser > 0")
    if r == 0:
        return pv / n
    k = (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    return pv * k

def eff_annual_from_monthly(rate_monthly: float) -> float:
    """CET anual equivalente sem tarifas adicionais: (1+i)^12 - 1"""
    r = float(rate_monthly)
    return (1.0 + r) ** 12 - 1.0

def amortization_schedule(pv: float, rate_monthly: float, n_months: int) -> List[Dict]:
    """Retorna lista de dicts com: periodo, saldo_ini, juros, amortizacao, parcela, saldo_fim"""
    saldo = float(pv)
    r = float(rate_monthly)
    n = int(n_months)
    pmt = pmt_price(r, n, saldo)
    rows = []
    for t in range(1, n + 1):
        juros = saldo * r
        amort = pmt - juros
        saldo_fim = saldo - amort
        rows.append(dict(
            periodo=t,
            saldo_ini=round(saldo, 2),
            juros=round(juros, 2),
            amortizacao=round(amort, 2),
            parcela=round(pmt, 2),
            saldo_fim=round(max(saldo_fim, 0.0), 2),
        ))
        saldo = saldo_fim
    return rows
