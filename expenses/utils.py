from twilio.rest import Client
from django.conf import settings

TRANSLATIONS = {
    'en': {
        'dashboard': 'Dashboard',
        'history': 'History',
        'analytics': 'Analytics',
        'budget': 'Budget Planner',
        'settings': 'Settings',
        'profile': 'Profile',
        'support': 'Support Helpdesk',
        'team': 'Team Management',
        'offers': 'Affiliate Offers',
        'total_spent': 'Total Spent',
        'monthly_budget': 'Monthly Budget Limit',
        'savings': 'Savings',
        'add_expense': 'Add New Expense',
        'category': 'Category',
        'description': 'Description',
        'amount': 'Amount',
        'payment_mode': 'Payment Mode',
        'action': 'Action',
        'streak': 'Savings Streak',
        'welcome': 'Welcome back,',
        'mfa_status': 'MFA Status',
        'language': 'Language',
        'currency': 'Currency',
        'timezone': 'Timezone',
        'logout': 'Logout',
        'billing': 'Billing & Checkout'
    },
    'es': {
        'dashboard': 'Panel de Control',
        'history': 'Historial',
        'analytics': 'Análisis',
        'budget': 'Plan de Presupuesto',
        'settings': 'Configuración',
        'profile': 'Perfil',
        'support': 'Soporte Técnico',
        'team': 'Gestión de Equipos',
        'offers': 'Ofertas de Afiliados',
        'total_spent': 'Total Gastado',
        'monthly_budget': 'Límite de Presupuesto',
        'savings': 'Ahorros',
        'add_expense': 'Agregar Gasto',
        'category': 'Categoría',
        'description': 'Descripción',
        'amount': 'Monto',
        'payment_mode': 'Método de Pago',
        'action': 'Acción',
        'streak': 'Racha de Ahorro',
        'welcome': 'Bienvenido de nuevo,',
        'mfa_status': 'Estado de MFA',
        'language': 'Idioma',
        'currency': 'Moneda',
        'timezone': 'Zona Horaria',
        'logout': 'Cerrar Sesión',
        'billing': 'Facturación y Pago'
    },
    'fr': {
        'dashboard': 'Tableau de bord',
        'history': 'Historique',
        'analytics': 'Analyses',
        'budget': 'Planificateur de budget',
        'settings': 'Paramètres',
        'profile': 'Profil',
        'support': 'Support technique',
        'team': 'Gestion d\'équipe',
        'offers': 'Offres affiliées',
        'total_spent': 'Total dépensé',
        'monthly_budget': 'Limite budgétaire',
        'savings': 'Épargne',
        'add_expense': 'Ajouter une dépense',
        'category': 'Catégorie',
        'description': 'Description',
        'amount': 'Montant',
        'payment_mode': 'Mode de paiement',
        'action': 'Action',
        'streak': 'Série d\'épargne',
        'welcome': 'Bon retour,',
        'mfa_status': 'Statut MFA',
        'language': 'Langue',
        'currency': 'Devise',
        'timezone': 'Fuseau horaire',
        'logout': 'Se déconnecter',
        'billing': 'Facturation & Paiement'
    },
    'hi': {
        'dashboard': 'डैशबोर्ड',
        'history': 'इतिहास',
        'analytics': 'विश्लेषण',
        'budget': 'बजट योजक',
        'settings': 'सेटिंग्स',
        'profile': 'प्रोफ़ाइल',
        'support': 'सहायता केंद्र',
        'team': 'टीम प्रबंधन',
        'offers': 'संबद्ध ऑफ़र',
        'total_spent': 'कुल खर्च',
        'monthly_budget': 'बजट सीमा',
        'savings': 'बचत',
        'add_expense': 'नया खर्च जोड़ें',
        'category': 'श्रेणी',
        'description': 'विवरण',
        'amount': 'राशि',
        'payment_mode': 'भुगतान का प्रकार',
        'action': 'कार्रवाई',
        'streak': 'बचत सिलसिला',
        'welcome': 'स्वागत है,',
        'mfa_status': 'एमएफए स्थिति',
        'language': 'भाषा',
        'currency': 'मुद्रा',
        'timezone': 'समय क्षेत्र',
        'logout': 'लॉगआउट',
        'billing': 'बिलिंग और चेकआउट'
    },
    'ar': {
        'dashboard': 'لوحة القيادة',
        'history': 'السجل',
        'analytics': 'التحليلات',
        'budget': 'مخطط الميزانية',
        'settings': 'الإعدادات',
        'profile': 'الملف الشخصي',
        'support': 'مكتب الدعم',
        'team': 'إدارة الفريق',
        'offers': 'عروض الأفلييت',
        'total_spent': 'إجمالي الإنفاق',
        'monthly_budget': 'حد الميزانية',
        'savings': 'المدخرات',
        'add_expense': 'إضافة مصروف',
        'category': 'الفئة',
        'description': 'الوصف',
        'amount': 'المبلغ',
        'payment_mode': 'طريقة الدفع',
        'action': 'الإجراء',
        'streak': 'سلسلة الادخار',
        'welcome': 'مرحباً بعودتك،',
        'mfa_status': 'حالة المصادقة الثنائية',
        'language': 'اللغة',
        'currency': 'العملة',
        'timezone': 'المنطقة الزمنية',
        'logout': 'تسجيل الخروج',
        'billing': 'الفواتير والدفع'
    }
}

def get_translation(key, lang_code='en'):
    lang = lang_code.lower() if lang_code else 'en'
    if lang not in TRANSLATIONS:
        lang = 'en'
    return TRANSLATIONS[lang].get(key, key)

def convert_currency(amount, from_curr, to_curr):
    if amount is None:
        return 0.0
    if from_curr == to_curr:
        return float(amount)
    
    rates = {
        'USD': 1.0,
        'INR': 83.0,
        'EUR': 0.92,
        'GBP': 0.79,
        'JPY': 156.0,
        'AED': 3.67,
        'SGD': 1.35,
        'AUD': 1.51,
        'CAD': 1.37,
    }
    
    from_rate = rates.get(from_curr, 1.0)
    to_rate = rates.get(to_curr, 1.0)
    
    amount_in_usd = float(amount) / from_rate
    converted_amount = amount_in_usd * to_rate
    return converted_amount


def format_currency(amount, currency_code, language_code='en'):
    if amount is None:
        amount = 0.0
    amount = float(amount)
    
    symbols = {
        'INR': '₹',
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'AED': 'د.إ',
        'SGD': 'S$',
        'AUD': 'A$',
        'CAD': 'C$'
    }
    symbol = symbols.get(currency_code, '$')
    lang = language_code.lower() if language_code else 'en'
    
    if currency_code == 'INR' or lang == 'hi':
        parts = f"{amount:.2f}".split('.')
        int_part = parts[0]
        dec_part = parts[1]
        if len(int_part) <= 3:
            formatted_int = int_part
        else:
            last_three = int_part[-3:]
            remaining = int_part[:-3]
            groups = []
            while len(remaining) > 2:
                groups.insert(0, remaining[-2:])
                remaining = remaining[:-2]
            if remaining:
                groups.insert(0, remaining)
            formatted_int = ','.join(groups) + ',' + last_three
        return f"{symbol}{formatted_int}.{dec_part}"
        
    elif currency_code == 'EUR' or lang in ['fr', 'es']:
        parts = f"{amount:.2f}".split('.')
        int_part = parts[0]
        dec_part = parts[1]
        groups = []
        while len(int_part) > 3:
            groups.insert(0, int_part[-3:])
            int_part = int_part[:-3]
        if int_part:
            groups.insert(0, int_part)
        formatted_int = '.'.join(groups)
        return f"{formatted_int},{dec_part} {symbol}"
        
    else:
        parts = f"{amount:.2f}".split('.')
        int_part = parts[0]
        dec_part = parts[1]
        groups = []
        while len(int_part) > 3:
            groups.insert(0, int_part[-3:])
            int_part = int_part[:-3]
        if int_part:
            groups.insert(0, int_part)
        formatted_int = ','.join(groups)
        return f"{symbol}{formatted_int}.{dec_part}"

def send_whatsapp_message(to_number, message):
    import sys
    if 'test' in sys.argv:
        return "mocked_sid_12345"
    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
    )
    from_number = settings.TWILIO_WHATSAPP_NUMBER
    if not from_number.startswith('whatsapp:'):
        from_number = f"whatsapp:{from_number}"
        
    if not to_number.startswith('whatsapp:'):
        to_number = f"whatsapp:{to_number}"
        
    message = client.messages.create(
        body=message,
        from_=from_number,
        to=to_number
    )
    return message.sid

def send_sms_message(to_number, message):
    import sys
    if 'test' in sys.argv:
        return "mocked_sms_sid_12345"
    client = Client(
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN
    )
    from_number = getattr(settings, 'TWILIO_WHATSAPP_NUMBER', '')
    if from_number.startswith('whatsapp:'):
        from_number = from_number.replace('whatsapp:', '')
    msg = client.messages.create(
        body=message,
        from_=from_number,
        to=to_number
    )
    return msg.sid

def send_notification_with_fallback(user, title, body):
    """
    Sends a notification with a cascading fallback strategy:
    WhatsApp -> Twilio SMS -> Email -> Dashboard Notification -> Audit Log.
    """
    from django.core.mail import send_mail
    from expenses.models import Notification, AuditLog
    import logging
    logger = logging.getLogger(__name__)
    
    profile = getattr(user, 'profile', None)
    whatsapp_number = profile.whatsapp_number if profile else None
    email = user.email if user else None
    
    sent = False
    error_log = []

    # 1. WhatsApp Attempt
    if whatsapp_number:
        try:
            to_number = whatsapp_number
            if not to_number.startswith('whatsapp:'):
                to_number = f"whatsapp:{to_number}"
            sid = send_whatsapp_message(to_number, body)
            if sid:
                sent = True
                logger.info(f"WhatsApp sent successfully to {whatsapp_number}")
                return "whatsapp"
        except Exception as e:
            error_log.append(f"WhatsApp failed: {str(e)}")

    # 2. Twilio SMS Attempt
    if not sent and whatsapp_number:
        try:
            to_number = whatsapp_number.replace('whatsapp:', '')
            sid = send_sms_message(to_number, body)
            if sid:
                sent = True
                logger.info(f"SMS sent successfully to {to_number}")
                return "sms"
        except Exception as e:
            error_log.append(f"SMS failed: {str(e)}")

    # 3. Email Attempt
    if not sent and email:
        try:
            send_mail(
                subject=title,
                message=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@smartspend.com'),
                recipient_list=[email],
                fail_silently=False
            )
            sent = True
            logger.info(f"Email sent successfully to {email}")
            return "email"
        except Exception as e:
            error_log.append(f"Email failed: {str(e)}")

    # 4. Dashboard Notification Attempt
    if not sent and user:
        try:
            Notification.objects.create(
                user=user,
                message=f"[{title}] {body}",
                status='unread'
            )
            sent = True
            logger.info(f"Dashboard Notification created for {user.username}")
            return "dashboard"
        except Exception as e:
            error_log.append(f"Dashboard Notification failed: {str(e)}")

    # 5. Audit Log Fallback
    try:
        AuditLog.objects.create(
            user=user if (user and user.is_authenticated) else None,
            action=f"Notification Cascade: Title: {title} | Body: {body[:100]}... | Errors: {', '.join(error_log)}"
        )
        logger.warning("Notification cascade logged to AuditLog.")
        return "audit_log"
    except Exception as e:
        logger.error(f"Critical notification failure. AuditLog failed: {str(e)}")
        return "failed"