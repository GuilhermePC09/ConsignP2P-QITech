from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter
def calculate_cet(monthly_rate):
    """Calculate annual CET (Custo Efetivo Total) from monthly rate"""
    try:
        monthly_rate_decimal = Decimal(str(monthly_rate))
        # Annual compound interest formula: (1 + monthly_rate/100)^12 - 1
        annual_rate = ((1 + monthly_rate_decimal/100) ** 12 - 1) * 100
        return round(annual_rate, 1)
    except (ValueError, TypeError, InvalidOperation):
        return monthly_rate


@register.filter
def format_currency(value):
    """Format number as Brazilian currency"""
    try:
        if value is None:
            return "0,00"
        value_decimal = Decimal(str(value))
        # Format with thousands separator and 2 decimal places
        return f"{value_decimal:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (ValueError, TypeError):
        return str(value)


@register.filter
def risk_level(rate):
    """Determine risk level based on interest rate"""
    try:
        rate_float = float(rate)
        if rate_float < 2.5:
            return "Baixo"
        elif rate_float < 3.5:
            return "Médio"
        else:
            return "Alto"
    except (ValueError, TypeError):
        return "Indefinido"


@register.filter
def risk_color(rate):
    """Get risk color based on interest rate"""
    try:
        rate_float = float(rate)
        if rate_float < 2.5:
            return "background:#E6F9ED;color:#059669"
        elif rate_float < 3.5:
            return "background:#FEF3C7;color:#B45309"
        else:
            return "background:#FEE2E2;color:#B91C1C"
    except (ValueError, TypeError):
        return "background:#F1F5F9;color:#6B7280"
