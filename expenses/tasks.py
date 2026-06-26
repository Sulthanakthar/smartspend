import os
import csv
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.core.management import call_command
try:
    from celery import shared_task
except ImportError:
    def shared_task(func):
        def delay(*args, **kwargs):
            return func(*args, **kwargs)
        func.delay = delay
        return func

logger = logging.getLogger(__name__)

@shared_task
def generate_pdf_invoice_task(payment_id):
    """
    Generates a ReportLab PDF billing invoice for a subscription payment
    and saves it under the SubscriptionInvoice model.
    """
    from expenses.models import SubscriptionPayment, SubscriptionInvoice
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    import io
    
    try:
        payment = SubscriptionPayment.objects.get(id=payment_id)
    except SubscriptionPayment.DoesNotExist:
        logger.error(f"Payment ID {payment_id} not found.")
        return False

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    styles = getSampleStyleSheet()
    
    # PDF styling
    title_style = ParagraphStyle(
        'InvoiceTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#6366f1'), spaceAfter=12
    )
    cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#1e293b'))
    header_style = ParagraphStyle('HeaderText', parent=styles['Normal'], fontSize=10, textColor=colors.white, fontName='Helvetica-Bold')

    story.append(Paragraph("SmartSpend - Tax Invoice", title_style))
    story.append(Paragraph(f"Invoice Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", cell_style))
    story.append(Paragraph(f"Customer: {payment.user.username} ({payment.user.email})", cell_style))
    story.append(Paragraph(f"Billing Cycle: {payment.billing_cycle.capitalize()}", cell_style))
    story.append(Spacer(1, 15))
    
    # Billing table details
    data = [
        [Paragraph('Plan Item', header_style), Paragraph('Price', header_style), Paragraph('Amount Billed', header_style)],
        [
            Paragraph(f"SmartSpend {payment.plan.capitalize()} Subscription", cell_style),
            Paragraph(f"{payment.amount} INR", cell_style),
            Paragraph(f"{payment.amount} INR", cell_style),
        ]
    ]
    
    t = Table(data, colWidths=[240, 150, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#6366f1')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t)
    doc.build(story)
    
    pdf_data = buffer.getvalue()
    buffer.close()
    
    # Save invoice details
    invoice_number = f"INV-{payment.id}-{datetime.now().strftime('%Y%m%d%H%M')}"
    invoice = SubscriptionInvoice(
        invoice_number=invoice_number,
        payment=payment,
        status='paid'
    )
    invoice.pdf_file.save(f"{invoice_number}.pdf", ContentFile(pdf_data))
    invoice.save()
    
    logger.info(f"Invoice {invoice_number} successfully generated for payment {payment_id}")
    return invoice.id

@shared_task
def export_report_task(user_id, format_type='csv', date_range='all'):
    """
    Builds CSV/Excel reports dynamically and creates a user Notification with file url.
    """
    from expenses.models import Expense, Notification
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"User ID {user_id} not found.")
        return False
        
    expenses = Expense.objects.filter(user=user)
    
    today = date.today()
    if date_range == 'monthly':
        start_date = date(today.year, today.month, 1)
        expenses = expenses.filter(expense_date__gte=start_date)
    elif date_range == 'weekly':
        start_date = today - timedelta(days=7)
        expenses = expenses.filter(expense_date__gte=start_date)

    file_name = f"export_{user.username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    media_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
    os.makedirs(media_dir, exist_ok=True)
    file_path = os.path.join(media_dir, file_name)
    
    # Generate CSV Report
    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Expense ID', 'Category', 'Description', 'Amount', 'Date', 'Payment Mode'])
        for exp in expenses:
            writer.writerow([
                exp.expense_id, exp.category, exp.description, exp.amount, exp.expense_date, exp.payment_mode
            ])
            
    # Create notification with direct media URL
    download_url = f"{settings.MEDIA_URL}exports/{file_name}"
    Notification.objects.create(
        user=user,
        message=f"📊 Your CSV financial report is ready for download! [Click here to download]({download_url})"
    )
    return file_path

@shared_task
def run_ai_forecasts_task(user_id):
    """
    Performs linear regression spending model calculation for the user.
    Uses clean mathematics formulas for regression slope and intercept.
    """
    from expenses.models import Expense, Notification
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return False
        
    expenses = Expense.objects.filter(user=user).order_by('expense_date')
    if expenses.count() < 3:
        # Not enough history to forecast
        return False
        
    # Standard Linear Regression: y = m*x + c
    # x = days offset from the first transaction date
    # y = cumulative amount spent
    start_date = expenses[0].expense_date
    x_coords = []
    y_coords = []
    
    running_total = Decimal('0.00')
    for exp in expenses:
        days = (exp.expense_date - start_date).days
        running_total += exp.amount
        x_coords.append(days)
        y_coords.append(float(running_total))
        
    n = len(x_coords)
    sum_x = sum(x_coords)
    sum_y = sum(y_coords)
    sum_xx = sum(x**2 for x in x_coords)
    sum_xy = sum(x*y for x, y in zip(x_coords, y_coords))
    
    denominator = (n * sum_xx - sum_x**2)
    if denominator == 0:
        slope = 0.0
        intercept = sum_y / n
    else:
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n
        
    # Forecast next 30 days cumulative spending
    projected_days = (date.today() - start_date).days + 30
    projected_spend = slope * projected_days + intercept
    
    Notification.objects.create(
        user=user,
        message=f"🔮 AI Spending Forecast updated: You are projected to spend a total of ₹{projected_spend:.2f} by the end of next month based on historical linear regression analysis."
    )
    return projected_spend

@shared_task
def create_database_backup_task():
    """
    Creates a backup snapshot of SQLite db file and saves it in backup folder.
    """
    db_path = settings.DATABASES['default']['NAME']
    if not os.path.exists(db_path):
        return False
        
    backup_dir = os.path.join(settings.BASE_DIR, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"db_backup_{timestamp}.sqlite3"
    backup_filepath = os.path.join(backup_dir, backup_filename)
    
    import shutil
    try:
        shutil.copy2(db_path, backup_filepath)
        logger.info(f"Database backup created: {backup_filename}")
        return backup_filepath
    except Exception as e:
        logger.error(f"Backup failed: {str(e)}")
        return False

@shared_task
def send_transactional_email_task(subject, recipient, body):
    """
    Asynchronously sends transactional emails using Django's email configuration.
    """
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@smartspend.com',
            recipient_list=[recipient],
            fail_silently=False
        )
        logger.info(f"Email sent to {recipient}")
        return True
    except Exception as e:
        logger.error(f"Email sending failed: {str(e)}")
        return False
