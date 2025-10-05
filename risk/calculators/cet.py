# -*- coding: utf-8 -*-
"""
Cálculo de CET (mensal e anual) por IRR de fluxos mensais.
- cet_from_flows: CET mensal e anual a partir de (desembolso líquido, parcelas, tarifas)
- irr_newton_bisection: solver robusto para TIR com fallback de bisseção

Modelo de fluxos (padrão Brasil/consignado simplificado):
t=0: +desembolso_liquido  (valor liberado ao cliente; ex.: pv - tarifa_entrada - iof)
t=1..n: -(parcela + tarifa_mensal)

Obs.: Se não houver tarifas, o CET mensal = rate_monthly e CET anual = (1+i)^12 - 1.
"""

from typing import Dict, Tuple, Optional, Callable
import math

def npv(rate: float, cashflows: list[float]) -> float:
    r = rate
    total = 0.0
    for t, cf in enumerate(cashflows):
        total += cf / ((1 + r) ** t)
    return total

def irr_newton_bisection(cashflows: list[float],
                         guess: float = 0.02,
                         max_iter: int = 100,
                         tol: float = 1e-10,
                         bracket: tuple[float, float] = (-0.9999, 1.0)) -> float:
    """
    Tenta Newton-Raphson; se divergir, cai para bisseção.
    Retorna taxa periódica (mensal) que zera o NPV dos fluxos.
    """
    # Derivada da NPV
    def dnpv(rate: float) -> float:
        s = 0.0
        for t, cf in enumerate(cashflows[1:], start=1):
            s -= t * cf / ((1 + rate) ** (t + 1))
        return s

    r = guess
    for _ in range(max_iter):
        f = npv(r, cashflows)
        if abs(f) < tol:
            return r
        df = dnpv(r)
        if df == 0 or not math.isfinite(df):
            break
        r_next = r - f / df
        if not math.isfinite(r_next) or r_next <= bracket[0] or r_next >= bracket[1]:
            break
        r = r_next

    # fallback: bisseção
    a, b = bracket
    fa, fb = npv(a, cashflows), npv(b, cashflows)
    # se não trocar sinal, tente expandir limites
    if fa * fb > 0:
        # ajuste grosseiro de limites
        a2, b2 = -0.9999, 3.0
        fa, fb = npv(a2, cashflows), npv(b2, cashflows)
        if fa * fb > 0:
            # último recurso: retorna palpite original
            return guess
        a, b = a2, b2
    for _ in range(200):
        m = (a + b) / 2.0
        fm = npv(m, cashflows)
        if abs(fm) < tol:
            return m
        if fa * fm <= 0:
            b, fb = m, fm
        else:
            a, fa = m, fm
    return (a + b) / 2.0

def cet_from_flows(pv: float,
                   rate_monthly: float,
                   n_months: int,
                   fees: Optional[Dict] = None) -> tuple[float, float]:
    """
    Calcula CET mensal e anual.
    fees (opcional):
      - upfront: valor em R$ descontado no desembolso (IOF/tarifa/seguro cobrança única)
      - monthly: valor em R$ adicionado à parcela todo mês
      - disbursement_discount: desconto adicional no t=0 (ex.: conta-salário, TED etc.)
    """
    pv = float(pv)
    r = float(rate_monthly)
    n = int(n_months)
    fees = fees or {}
    upfront = float(fees.get("upfront", 0.0))
    monthly_fee = float(fees.get("monthly", 0.0))
    disc0 = float(fees.get("disbursement_discount", 0.0))

    # parcela pela Price
    from risk.calculators.pmt import pmt_price, eff_annual_from_monthly
    pmt = pmt_price(r, n, pv)

    # fluxos:
    desembolso_liquido = pv - upfront - disc0
    cashflows = [desembolso_liquido] + [-(pmt + monthly_fee)] * n

    # IRR mensal
    cet_m = irr_newton_bisection(cashflows, guess=r)
    cet_y = (1.0 + cet_m) ** 12 - 1.0
    return float(cet_m), float(cet_y)
