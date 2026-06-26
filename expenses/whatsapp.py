import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def safe_print(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        try:
            print(msg.encode('ascii', errors='replace').decode('ascii'))
        except Exception:
            pass


def send_whatsapp_admin_notification(message: str) -> bool:
    """
    Send a WhatsApp notification to the admin number using Twilio.
    Accepts a single pre-formatted message string.
    """
    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
    from_number = getattr(settings, 'TWILIO_WHATSAPP_NUMBER', None)
    to_number = getattr(settings, 'ADMIN_WHATSAPP_NUMBER', None)

    if not account_sid or not auth_token:
        logger.warning("Twilio credentials missing in settings.")
        safe_print("⚠️  Twilio credentials missing.")
        return False

    if not from_number or not to_number:
        logger.warning("WhatsApp phone numbers missing in settings.")
        safe_print("⚠️  WhatsApp numbers missing.")
        return False

    try:
        import sys
        if 'test' in sys.argv:
            safe_print(f"✅ WhatsApp Sent (Mocked for Test): {message[:100]}...")
            return True

        from twilio.rest import Client

        # Ensure whatsapp: prefix
        if not from_number.startswith('whatsapp:'):
            from_number = f"whatsapp:{from_number}"
        if not to_number.startswith('whatsapp:'):
            to_number = f"whatsapp:{to_number}"

        client = Client(account_sid, auth_token)
        sent = client.messages.create(body=message, from_=from_number, to=to_number)

        logger.info(f"WhatsApp message sent: {sent.sid}")
        safe_print(f"✅ WhatsApp Sent: {sent.sid}")
        return True

    except Exception as e:
        logger.error(f"Twilio error: {e}")
        safe_print(f"❌ Twilio Error: {e}")
        return False


def send_expense_alert(expense_name: str, amount, category: str, total_expense) -> bool:
    """Convenience wrapper for expense-added alerts."""
    message = (
        f"💰 *SmartSpend Expense Alert*\n\n"
        f"📝 Expense: {expense_name}\n"
        f"💵 Amount: ₹{amount}\n"
        f"📂 Category: {category}\n"
        f"📊 Total This Month: ₹{total_expense}\n\n"
        f"✅ Expense Added Successfully"
    )
    return send_whatsapp_admin_notification(message)