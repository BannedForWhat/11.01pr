from django import template
register = template.Library()

@register.filter
def fmt_number(value, pattern='1 234,56'):
    try:
        x = float(value)
    except Exception:
        return value
    s = f"{x:,.2f}"
    s = s.replace(',', ' ').replace('.', ',')
    return s