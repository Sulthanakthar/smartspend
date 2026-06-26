from django import template
from expenses.utils import get_translation, format_currency as utils_format_currency

register = template.Library()

@register.filter(name='translate')
def translate_filter(key, lang_code='en'):
    return get_translation(key, lang_code)

@register.filter(name='format_currency')
def format_currency_filter(amount, profile):
    if not profile:
        return f"₹{amount}"
    # profile can be a Profile instance or user object if accessed as user.profile
    # Let's handle both gracefully
    if hasattr(profile, 'profile'):
        profile_obj = profile.profile
    else:
        profile_obj = profile
    
    currency = getattr(profile_obj, 'currency', 'INR')
    language = getattr(profile_obj, 'language', 'en')
    return utils_format_currency(amount, currency, language)
