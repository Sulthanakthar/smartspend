import csv
import random
import string
import json
from datetime import date, timedelta, datetime
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.conf import settings

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from .models import Expense, Budget, Profile, CATEGORY_CHOICES, UserActivityLog, Notification, SavingsChallenge, Team, SupportTicket, AdminNotification, CouponRedemption, Offer, OfferClick, OfferConversion, TicketReply, TicketAttachment, Vendor, MarketplaceProduct, MarketplaceOrder
from .forms import RegisterForm, ProfileForm, ExpenseForm, BudgetForm
from .nlp import parse_expense_text, parse_bank_sms
from .chatbot import get_chatbot_response
from .utils import send_whatsapp_message


# Helper to load preferences
def get_user_preferences(request):
    if request.user.is_authenticated:
        profile, created = Profile.objects.get_or_create(user=request.user)
        # Currency symbols mapping
        symbols = {
            'INR': '₹', 'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'AED': 'د.إ', 'SGD': 'S$'
        }
        return {
            'currency_symbol': symbols.get(profile.currency, '$'),
            'currency': profile.currency,
            'theme': profile.theme,
            'language': profile.language,
            'timezone': profile.timezone,
            'mfa_enabled': profile.mfa_enabled,
            'voice_rate': profile.voice_rate,
            'notifications_enabled': profile.notifications_enabled,
        }
    return {
        'currency_symbol': '₹',
        'currency': 'INR',
        'theme': 'dark',
        'language': 'en',
        'timezone': 'UTC',
        'mfa_enabled': False,
        'voice_rate': 1.0,
        'notifications_enabled': True,
    }

# Helper to generate AI insights
def get_ai_insights(user):
    today = date.today()
    start_of_month = date(today.year, today.month, 1)
    
    # Previous month boundaries
    last_month_end = start_of_month - timedelta(days=1)
    last_month_start = date(last_month_end.year, last_month_end.month, 1)
    
    # Calculate totals
    current_month_total = Expense.objects.filter(user=user, expense_date__gte=start_of_month).aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
    last_month_total = Expense.objects.filter(user=user, expense_date__range=[last_month_start, last_month_end]).aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
    
    insights = []
    
    # Insight 1: Month-on-Month comparison
    if last_month_total > 0:
        diff_pct = ((current_month_total - last_month_total) / last_month_total) * 100
        if diff_pct > 10:
            insights.append(f"⚠️ Spending is up by **{diff_pct:.1f}%** compared to last month. Consider reviewing non-essential items.")
        elif diff_pct < -10:
            insights.append(f"🎉 Great job! You have spent **{abs(diff_pct):.1f}%** less than last month so far.")
        else:
            insights.append("📊 Your spending is tracking stably compared to last month.")
    else:
        insights.append("🌱 You are in your first months of tracking. Keep speaking your expenses to build predictions!")

    # Insight 2: Category share
    top_cat = Expense.objects.filter(user=user, expense_date__gte=start_of_month).values('category').annotate(t=Sum('amount')).order_by('-t').first()
    if top_cat and current_month_total > 0:
        pct = (top_cat['t'] / current_month_total) * 100
        if pct > 35:
            insights.append(f"🍕 **{top_cat['category']}** accounts for **{pct:.1f}%** of your monthly expenses. Consider setting a strict budget limit.")
        else:
            insights.append(f"💼 Your highest spending category is **{top_cat['category']}** at **{pct:.1f}%**.")

    # Insight 3: Budget check
    budgets = Budget.objects.filter(user=user)
    over_budget_cats = []
    for b in budgets:
        cat_total = Expense.objects.filter(user=user, category=b.category, expense_date__gte=start_of_month).aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
        if cat_total > b.limit_amount:
            over_budget_cats.append(b.category)
            
    if over_budget_cats:
        insights.append(f"🚨 You have exceeded your budget limits in: **{', '.join(over_budget_cats)}**!")
    else:
        insights.append("💡 All categories are currently within budget parameters.")

    # NEW Insight 4: Dynamic Savings Recommendation
    if current_month_total > 0:
        potential_savings = float(current_month_total) * 0.15
        insights.append(f"💡 AI Recommendation: Reducing unnecessary purchases could optimize savings by **₹{potential_savings:.2f}** this month.")

    # NEW Insight 5: Spending Forecast
    all_expenses = Expense.objects.filter(user=user)
    if all_expenses.count() >= 3:
        first_exp = all_expenses.order_by('expense_date').first()
        days_diff = (today - first_exp.expense_date).days or 1
        total_historical = all_expenses.aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
        daily_avg = float(total_historical) / days_diff
        forecast = daily_avg * 30
        insights.append(f"🔮 Spend Forecast: Based on historical patterns, you are projected to spend **₹{forecast:.2f}** next month.")

    return insights

# Landing View
def landing(request):
    return render(request, 'expenses/landing.html')

# Register View
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    # Track referral code in session if present in URL
    ref_code = request.GET.get('ref')
    if ref_code:
        request.session['ref_code'] = ref_code
    else:
        ref_code = request.session.get('ref_code')
    
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            # Log registration event
            AdminNotification.objects.create(
                event_type='user_registration',
                message=f"New user registered: {user.username} (Email: {user.email or 'N/A'})"
            )
            
            # Retrieve profile
            profile = user.profile
            
            # Process referral link reward
            if ref_code:
                referrer_profile = Profile.objects.filter(referral_code=ref_code).first()
                if referrer_profile:
                    profile.referred_by = referrer_profile.user
                    profile.subscription_tier = 'pro'
                    profile.subscription_end_date = date.today() + timedelta(days=14)
                    profile.save()
                    
                    # Reward referrer
                    referrer_profile.subscription_tier = 'pro'
                    ref_end = referrer_profile.subscription_end_date or date.today()
                    referrer_profile.subscription_end_date = max(ref_end, date.today()) + timedelta(days=14)
                    referrer_profile.save()
                    
                    # Log activity and notify
                    UserActivityLog.objects.create(
                        user=referrer_profile.user,
                        action=f"Referred user registered: {user.username}. Awarded 14 days Pro subscription."
                    )
                    Notification.objects.create(
                        user=referrer_profile.user,
                        message=f"🎉 Referral reward applied! You received 14 days of Pro for inviting {user.username}."
                    )
                    Notification.objects.create(
                        user=user,
                        message="🎉 Referral signup reward applied! You received 14 days of Pro."
                    )

            # Clear session ref_code
            if 'ref_code' in request.session:
                del request.session['ref_code']
                
            # Authenticate and login
            user_auth = authenticate(username=user.username, password=form.cleaned_data['password'])
            if user_auth:
                login(request, user_auth)
                return redirect('dashboard')
    else:
        form = RegisterForm()
        
    return render(request, 'expenses/register.html', {'form': form})

# Login View
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user:
            profile, _ = Profile.objects.get_or_create(user=user)
            if profile.mfa_enabled:
                request.session['mfa_user_id'] = user.id
                request.session['mfa_next_url'] = 'dashboard'
                import random
                otp = f"{random.randint(100000, 999999)}"
                profile.otp_code = otp
                profile.otp_expiry = timezone.now() + timedelta(minutes=5)
                profile.save()
                
                print(f"\n========================================")
                print(f"MFA OTP Code for {user.username}: {otp}")
                print(f"========================================\n")
                
                UserActivityLog.objects.create(
                    user=user,
                    action="MFA OTP generated for standard login"
                )
                return redirect('otp_verify')
            else:
                login(request, user)
                return redirect('dashboard')
        else:
            error = "Invalid username or password."
            AdminNotification.objects.create(
                event_type='failed_login',
                message=f"Failed login attempt for username: {username}"
            )
            
    return render(request, 'expenses/login.html', {'error': error})

# Admin Login View
def admin_login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('admin_dashboard')
        return redirect('dashboard')
        
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username, password=password)
        if user:
            if user.is_staff or user.is_superuser:
                profile, _ = Profile.objects.get_or_create(user=user)
                if profile.mfa_enabled:
                    request.session['mfa_user_id'] = user.id
                    request.session['mfa_next_url'] = 'admin_dashboard'
                    import random
                    otp = f"{random.randint(100000, 999999)}"
                    profile.otp_code = otp
                    profile.otp_expiry = timezone.now() + timedelta(minutes=5)
                    profile.save()
                    
                    print(f"\n========================================")
                    print(f"MFA OTP Code for admin {user.username}: {otp}")
                    print(f"========================================\n")
                    
                    UserActivityLog.objects.create(
                        user=user,
                        action="MFA OTP generated for admin login"
                    )
                    return redirect('otp_verify')
                else:
                    login(request, user)
                    return redirect('admin_dashboard')
            else:
                error = "Access Denied: You do not have administrator permissions."
                AdminNotification.objects.create(
                    event_type='failed_login',
                    message=f"Failed admin login (Access Denied) for username: {username}"
                )
        else:
            error = "Invalid username or password."
            AdminNotification.objects.create(
                event_type='failed_login',
                message=f"Failed admin login attempt for username: {username}"
            )
            
    return render(request, 'expenses/login.html', {'error': error, 'is_admin_login': True})

# OTP Verification View
def otp_verify(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    user_id = request.session.get('mfa_user_id')
    if not user_id:
        return redirect('login')
        
    user = get_object_or_404(User, id=user_id)
    profile = user.profile
    error = None
    
    if request.method == 'POST':
        otp_entered = request.POST.get('otp', '').strip()
        if profile.otp_code == otp_entered and profile.otp_expiry and profile.otp_expiry > timezone.now():
            profile.otp_code = None
            profile.otp_expiry = None
            profile.save()
            
            login(request, user)
            
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')
            UserActivityLog.objects.create(
                user=user,
                action="Logged in successfully (MFA verified)",
                ip_address=ip
            )
            
            next_url = request.session.get('mfa_next_url', 'dashboard')
            # Clean session variables
            del request.session['mfa_user_id']
            if 'mfa_next_url' in request.session:
                del request.session['mfa_next_url']
                
            return redirect(next_url)
        else:
            error = "Invalid or expired OTP code."
            
    return render(request, 'expenses/otp.html', {'error': error, 'username': user.username})


# Logout View
def logout_view(request):
    logout(request)
    return redirect('landing')

# Dashboard View
@login_required
def dashboard(request):
    prefs = get_user_preferences(request)
    today = date.today()
    start_of_month = date(today.year, today.month, 1)
    
    # Expenses current month
    current_month_expenses = Expense.objects.filter(user=request.user, expense_date__gte=start_of_month)
    total_expense = current_month_expenses.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    
    # Highest category
    highest_cat_q = current_month_expenses.values('category').annotate(t=Sum('amount')).order_by('-t').first()
    highest_category = highest_cat_q['category'] if highest_cat_q else 'None'
    highest_cat_amount = highest_cat_q['t'] if highest_cat_q else Decimal(0.0)
    
    # Recent Transactions
    recent_transactions = Expense.objects.filter(
    user=request.user
).order_by('-expense_date')[:5]
    
    # Budgets progress
    budgets = Budget.objects.filter(user=request.user)
    budget_progress = []
    budget_alerts = []
    for b in budgets:
        spent = current_month_expenses.filter(category=b.category).aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
        if b.limit_amount and b.limit_amount > 0:
            percentage = min(int((spent / b.limit_amount) * 100), 100)
        else:
            percentage = 0
        budget_progress.append({
            'category': b.category,
            'limit': b.limit_amount,
            'spent': spent,
            'percentage': percentage
        })
        if spent > b.limit_amount:
            budget_alerts.append(f"Exceeded your {b.category} budget by {prefs['currency_symbol']}{spent - b.limit_amount:.2f}!")
        elif spent > b.limit_amount * Decimal(0.8):
            budget_alerts.append(f"Approaching limit for {b.category} budget (80%+ spent).")

    # Dynamic AI insights
    insights = get_ai_insights(request.user)
    
    # Standard Forms for Modals
    expense_form = ExpenseForm(initial={'expense_date': today})
    budget_form = BudgetForm()

    context = {
        'total_expense': total_expense,
        'highest_category': highest_category,
        'highest_cat_amount': highest_cat_amount,
        'recent_transactions': recent_transactions,
        'budget_progress': budget_progress,
        'budget_alerts': budget_alerts,
        'insights': insights,
        'expense_form': expense_form,
        'budget_form': budget_form,
        'prefs': prefs,
        'CATEGORY_CHOICES': CATEGORY_CHOICES,
    }
    return render(request, 'expenses/dashboard.html', context)

# Expense History View (Search, Filter, Actions)
@login_required
def expense_history(request):
    prefs = get_user_preferences(request)
    expenses = Expense.objects.filter(user=request.user)
    
    # Search and Filter parameters
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    
    if query:
        expenses = expenses.filter(description__icontains=query)
    if category:
        expenses = expenses.filter(category=category)
    if start_date:
        expenses = expenses.filter(expense_date__gte=start_date)
    if end_date:
        expenses = expenses.filter(expense_date__lte=end_date)
        
    categories = [c[0] for c in CATEGORY_CHOICES]
    expense_form = ExpenseForm(initial={'expense_date': date.today()})

    context = {
        'expenses': expenses,
        'categories': categories,
        'query': query,
        'selected_category': category,
        'start_date': start_date,
        'end_date': end_date,
        'expense_form': expense_form,
        'prefs': prefs,
    }
    return render(request, 'expenses/history.html', context)

# Analytics Page View
@login_required
def analytics_page(request):
    prefs = get_user_preferences(request)
    range_type = request.GET.get('range', 'monthly')
    today = date.today()
    
    if range_type == 'daily':
        start_date = today
        end_date = today
        start_prev = today - timedelta(days=1)
        end_prev = today - timedelta(days=1)
    elif range_type == 'weekly':
        start_date = today - timedelta(days=7)
        end_date = today
        start_prev = today - timedelta(days=14)
        end_prev = today - timedelta(days=8)
    elif range_type == 'yearly':
        start_date = date(today.year, 1, 1)
        end_date = today
        start_prev = date(today.year - 1, 1, 1)
        end_prev = date(today.year - 1, 12, 31)
    else: # monthly (default)
        range_type = 'monthly'
        start_date = date(today.year, today.month, 1)
        end_date = today
        if today.month == 1:
            start_prev = date(today.year - 1, 12, 1)
            end_prev = date(today.year - 1, 12, 31)
        else:
            start_prev = date(today.year, today.month - 1, 1)
            end_prev = start_date - timedelta(days=1)

    this_period_total = Expense.objects.filter(user=request.user, expense_date__gte=start_date, expense_date__lte=end_date).aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
    prev_period_total = Expense.objects.filter(user=request.user, expense_date__gte=start_prev, expense_date__lte=end_prev).aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
    
    change_pct = 0.0
    if prev_period_total > 0:
        change_pct = float((this_period_total - prev_period_total) / prev_period_total) * 100
        
    # Transaction counts and average sizes
    this_period_expenses = Expense.objects.filter(user=request.user, expense_date__gte=start_date, expense_date__lte=end_date)
    total_count = this_period_expenses.count()
    average_order_value = float(this_period_total) / total_count if total_count > 0 else 0.0
    
    # Category Distribution (Pie Chart)
    cat_distribution = Expense.objects.filter(user=request.user, expense_date__gte=start_date, expense_date__lte=end_date) \
        .values('category').annotate(total=Sum('amount')).order_by('-total')
    
    # Comparison (Bar Chart) - Past 6 periods
    six_months_ago = today - timedelta(days=180)
    monthly_data = Expense.objects.filter(user=request.user, expense_date__gte=six_months_ago) \
        .annotate(month=TruncMonth('expense_date')) \
        .values('month').annotate(total=Sum('amount')).order_by('month')
    
    # Daily Trend for Current Period (Line Chart)
    daily_data = Expense.objects.filter(user=request.user, expense_date__gte=start_date, expense_date__lte=end_date) \
        .values('expense_date').annotate(total=Sum('amount')).order_by('expense_date')

    # Convert querysets to lists for JSON
    pie_labels = [item['category'] for item in cat_distribution]
    pie_values = [float(item['total']) for item in cat_distribution]
    
    bar_labels = [item['month'].strftime('%b %Y') for item in monthly_data]
    bar_values = [float(item['total']) for item in monthly_data]
    
    line_labels = [item['expense_date'].strftime('%d %b') for item in daily_data]
    line_values = [float(item['total']) for item in daily_data]

    # Predict Next Month's Spending
    all_expenses = Expense.objects.filter(user=request.user)
    prediction = None
    if all_expenses.count() >= 3:
        first_expense = all_expenses.order_by('expense_date').first()
        days_diff = (today - first_expense.expense_date).days or 1
        total_historical = all_expenses.aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
        daily_average = float(total_historical) / days_diff
        prediction = daily_average * 30

    # Detailed Category Breakdown Table
    category_breakdown = []
    cat_totals = this_period_expenses.values('category').annotate(
        total_spent=Sum('amount'),
        order_count=Count('expense_id'),
        avg_spent=Avg('amount')
    ).order_by('-total_spent')
    
    budgets = Budget.objects.filter(user=request.user)
    budget_dict = {b.category: b.limit_amount for b in budgets}
    
    for item in cat_totals:
        cat_name = item['category']
        spent = item['total_spent']
        count = item['order_count']
        avg = float(item['avg_spent'])
        limit = budget_dict.get(cat_name, Decimal(0.0))
        
        pct_of_total = (float(spent) / float(this_period_total) * 100) if this_period_total > 0 else 0.0
        
        status = "normal"
        if limit > 0:
            if spent >= limit:
                status = "exceeded"
            elif spent >= limit * Decimal(0.8):
                status = "warning"
                
        category_breakdown.append({
            'category': cat_name,
            'total_spent': spent,
            'count': count,
            'avg_spent': avg,
            'limit': limit,
            'pct_of_total': pct_of_total,
            'status': status
        })

    context = {
        'pie_labels': pie_labels,
        'pie_values': pie_values,
        'bar_labels': bar_labels,
        'bar_values': bar_values,
        'line_labels': line_labels,
        'line_values': line_values,
        'prediction': prediction,
        'this_month_total': this_period_total,
        'last_month_total': prev_period_total,
        'change_pct': change_pct,
        'total_count': total_count,
        'average_order_value': average_order_value,
        'category_breakdown': category_breakdown,
        'prefs': prefs,
        'range_type': range_type,
    }
    return render(request, 'expenses/analytics.html', context)


# Budget Planner View
@login_required
def budget_planner(request):
    prefs = get_user_preferences(request)
    categories = [c[0] for c in CATEGORY_CHOICES]
    
    if request.method == 'POST':
        # Add or update budget
        category = request.POST.get('category')
        limit_amount = request.POST.get('limit_amount')
        if category and limit_amount:
            budget, created = Budget.objects.update_or_create(
                user=request.user,
                category=category,
                defaults={'limit_amount': Decimal(limit_amount)}
            )
            AdminNotification.objects.create(
                event_type='budget_change',
                message=f"User {request.user.username} {'created' if created else 'updated'} budget for '{category}' to {limit_amount} INR"
            )
            return redirect('budget_planner')

    # Fetch budgets list
    budgets = Budget.objects.filter(user=request.user)
    budget_dict = {b.category: b.limit_amount for b in budgets}
    
    # Build list containing budget and current spent
    today = date.today()
    start_of_month = date(today.year, today.month, 1)
    
    budget_list = []
    for cat in categories:
        budget_obj = budgets.filter(category=cat).first()
        limit = budget_obj.limit_amount if budget_obj else Decimal(0.0)
        budget_id = budget_obj.budget_id if budget_obj else None
        spent = Expense.objects.filter(user=request.user, category=cat, expense_date__gte=start_of_month).aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
        percentage = min(int((spent / limit) * 100), 100) if limit > 0 else 0
        remaining = max(limit - spent, Decimal(0.0))
        over_by = max(spent - limit, Decimal(0.0))
        budget_list.append({
            'budget_id': budget_id,
            'category': cat,
            'limit': limit,
            'spent': spent,
            'percentage': percentage,
            'remaining': remaining,
            'over_by': over_by
        })

    budget_form = BudgetForm()
    context = {
        'budget_list': budget_list,
        'categories': categories,
        'budget_form': budget_form,
        'prefs': prefs,
    }
    return render(request, 'expenses/budget.html', context)

@login_required
def settings_page(request):
    prefs = get_user_preferences(request)
    profile = request.user.profile
    
    if request.method == 'POST':
        theme = request.POST.get('theme', 'dark')
        currency = request.POST.get('currency', 'INR')
        language = request.POST.get('language', 'en')
        timezone = request.POST.get('timezone', 'UTC')
        voice_rate = request.POST.get('voice_rate', 1.0)
        notifications_enabled = 'notifications_enabled' in request.POST
        mfa_enabled = 'mfa_enabled' in request.POST
        
        profile.theme = theme
        profile.currency = currency
        profile.language = language
        profile.timezone = timezone
        profile.voice_rate = float(voice_rate)
        profile.notifications_enabled = notifications_enabled
        profile.mfa_enabled = mfa_enabled
        profile.save()
        return redirect('settings')
        
    timezones = [
        ('UTC', 'UTC (Coordinated Universal Time)'),
        ('Asia/Kolkata', 'India (IST - Asia/Kolkata)'),
        ('America/New_York', 'US East (EST/EDT - America/New_York)'),
        ('America/Toronto', 'Canada (EST/EDT - America/Toronto)'),
        ('Europe/London', 'United Kingdom (GMT/BST - Europe/London)'),
        ('Europe/Paris', 'Europe (CET/CEST - Europe/Paris)'),
        ('Australia/Sydney', 'Australia (AEDT/AEST - Australia/Sydney)'),
        ('Asia/Dubai', 'Middle East (GST - Asia/Dubai)'),
        ('Asia/Singapore', 'Singapore (SGT - Asia/Singapore)'),
    ]
    
    context = {
        'prefs': prefs,
        'profile': profile,
        'currency_choices': Profile._meta.get_field('currency').choices,
        'timezones': timezones,
    }
    return render(request, 'expenses/settings.html', context)

# ─── GDPR Data & Privacy Views ───────────────────────────────────────────────
@login_required
def gdpr_export_data(request):
    user = request.user
    profile = getattr(user, 'profile', None)
    
    data = {
        'user_details': {
            'username': user.username,
            'email': user.email,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
            'subscription_tier': profile.subscription_tier if profile else 'free',
            'role': profile.role if profile else 'user',
            'currency': profile.currency if profile else 'INR',
            'timezone': profile.timezone if profile else 'UTC',
            'language': profile.language if profile else 'en',
            'mfa_enabled': profile.mfa_enabled if profile else False
        },
        'expenses': [
            {
                'expense_id': e.expense_id,
                'category': e.category,
                'description': e.description,
                'amount': float(e.amount),
                'expense_date': e.expense_date.isoformat(),
                'payment_mode': e.payment_mode
            } for e in user.expenses.all()
        ],
        'budgets': [
            {
                'category': b.category,
                'limit_amount': float(b.limit_amount)
            } for b in user.budgets.all()
        ],
        'support_tickets': [
            {
                'ticket_id': t.ticket_id,
                'subject': t.subject,
                'message': t.message,
                'status': t.status,
                'created_at': t.created_at.isoformat() if t.created_at else None
            } for t in user.support_tickets.all()
        ],
        'activity_logs': [
            {
                'action': log.action,
                'timestamp': log.timestamp.isoformat(),
                'ip_address': log.ip_address
            } for log in user.activity_logs.all()
        ]
    }
    
    response_content = json.dumps(data, indent=4)
    response = HttpResponse(response_content, content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="smartspend_data_{user.username}.json"'
    
    UserActivityLog.objects.create(
        user=user,
        action="Exported personal account data via GDPR controls"
    )
    return response

@login_required
def gdpr_delete_account(request):
    if request.method == 'POST':
        user = request.user
        username = user.username
        from django.contrib.auth import logout
        
        UserActivityLog.objects.create(
            user=None,
            action=f"User {username} deleted their account and purged all personal data"
        )
        
        logout(request)
        user.delete()
        return redirect('landing')
    return redirect('settings')

# Profile Management View
@login_required
def profile_page(request):
    prefs = get_user_preferences(request)
    profile, created = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile, initial={
            'username': request.user.username,
            'email': request.user.email
        })
        if form.is_valid():
            # Save user attributes
            request.user.username = form.cleaned_data['username']
            request.user.email = form.cleaned_data['email']
            request.user.save()
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile, initial={
            'username': request.user.username,
            'email': request.user.email
        })
        
    context = {
        'form': form,
        'prefs': prefs,
    }
    return render(request, 'expenses/profile.html', context)

# Custom Admin Dashboard View (Superuser/Admin/Staff Only)
@login_required
def custom_admin_dashboard(request):
    if not (request.user.is_staff or request.user.profile.role in ['super_admin', 'admin', 'support_staff']):
        return redirect('dashboard')
        
    prefs = get_user_preferences(request)
    users = User.objects.select_related('profile').annotate(
        expense_count=Count('expenses'),
        total_spent=Sum('expenses__amount'),
        budget_count=Count('budgets', distinct=True)
    ).order_by('-date_joined')
    
    # Fetch subscription details
    pro_count = Profile.objects.filter(subscription_tier='pro').count()
    business_count = Profile.objects.filter(subscription_tier='business').count()
    enterprise_count = Profile.objects.filter(subscription_tier='enterprise').count()
    total_paying = pro_count + business_count + enterprise_count
    
    # Calculate MRR & ARR in USD
    mrr = (pro_count * 9.99) + (business_count * 19.99) + (enterprise_count * 49.99)
    arr = mrr * 12
    
    # Calculate LTV: ARPU / Churn Rate
    arpu = mrr / total_paying if total_paying > 0 else 0.0
    churn_rate = 5.0 # 5% Churn Rate baseline
    retention_rate = 100.0 - churn_rate
    ltv = arpu / (churn_rate / 100.0) if total_paying > 0 else 0.0
    cac = 12.50 # $12.50 acquisition cost baseline
    
    # Growth metrics (last 30 days vs previous 30 days)
    total_users = User.objects.count()
    joined_last_30 = User.objects.filter(date_joined__gte=timezone.now() - timedelta(days=30)).count()
    prev_users = total_users - joined_last_30
    user_growth = (joined_last_30 / prev_users * 100) if prev_users > 0 else 100.0

    # DAU/WAU/MAU Calculation
    today_dt = timezone.now()
    dau = UserActivityLog.objects.filter(timestamp__gte=today_dt - timedelta(days=1)).values('user').distinct().count()
    wau = UserActivityLog.objects.filter(timestamp__gte=today_dt - timedelta(days=7)).values('user').distinct().count()
    mau = UserActivityLog.objects.filter(timestamp__gte=today_dt - timedelta(days=30)).values('user').distinct().count()
    dau = max(dau, 1)
    wau = max(wau, 1)
    mau = max(mau, 1)

    # Database Size (Health Monitoring)
    import os
    from django.conf import settings
    db_size_mb = 0.0
    try:
        db_path = settings.DATABASES['default']['NAME']
        if os.path.exists(db_path):
            db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
    except Exception:
        pass
        
    system_stats = {
        'total_users': total_users,
        'total_expenses': Expense.objects.count(),
        'total_value': Expense.objects.aggregate(t=Sum('amount'))['t'] or Decimal(0.0),
        'avg_expense': Expense.objects.aggregate(a=Avg('amount'))['a'] or Decimal(0.0),
        'premium_count': pro_count,
        'professional_count': business_count,
        'enterprise_count': enterprise_count,
        'mrr': mrr,
        'arr': arr,
        'ltv': ltv,
        'cac': cac,
        'ltv_cac_ratio': ltv / cac if cac > 0 else 0.0,
        'churn_rate': churn_rate,
        'retention_rate': retention_rate,
        'user_growth': user_growth,
        'db_size_mb': db_size_mb,
        'dau': dau,
        'wau': wao if 'wao' in locals() else wau, # safety check
        'mau': mau,
    }
    
    activity_logs = UserActivityLog.objects.all().order_by('-timestamp')[:50]
    tickets = SupportTicket.objects.all().order_by('-created_at')
    
    # Database Table row counts
    from expenses.models import AuditLog, SubscriptionPayment
    db_table_counts = [
        {'table': 'Users (auth_user)', 'count': User.objects.count()},
        {'table': 'Expenses (expenses_expense)', 'count': Expense.objects.count()},
        {'table': 'Budgets (expenses_budget)', 'count': Budget.objects.count()},
        {'table': 'Profiles (expenses_profile)', 'count': Profile.objects.count()},
        {'table': 'Payments (expenses_subscriptionpayment)', 'count': SubscriptionPayment.objects.count()},
        {'table': 'Audit Logs (expenses_auditlog)', 'count': AuditLog.objects.count()},
    ]

    # Slow Queries log reader
    slow_queries_list = []
    log_path = os.path.join(settings.BASE_DIR, 'slow_queries.log')
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in reversed(lines[-15:]):
                    slow_queries_list.append(line.strip())
        except Exception:
            pass

    # Scorecard readiness calculation
    security_checks = {
        'debug_mode_disabled': not settings.DEBUG,
        'security_middleware_active': 'django.middleware.security.SecurityMiddleware' in settings.MIDDLEWARE,
        'csrf_middleware_active': 'django.middleware.csrf.CsrfViewMiddleware' in settings.MIDDLEWARE,
        'mfa_enabled_users': Profile.objects.filter(mfa_enabled=True).exists(),
    }
    security_score = sum([25 for k, v in security_checks.items() if v])
    
    slow_count = len(slow_queries_list)
    performance_score = max(50, 100 - (slow_count * 5))
    
    accessibility_score = 95
    if Profile.objects.filter(theme='high-contrast').exists():
        accessibility_score = 100
        
    seo_score = 100
    overall_score = int((security_score + performance_score + accessibility_score + seo_score) / 4)
    
    readiness_scorecard = {
        'security_score': security_score,
        'security_checks': security_checks,
        'performance_score': performance_score,
        'accessibility_score': accessibility_score,
        'seo_score': seo_score,
        'overall_score': overall_score,
    }

    offers_list = Offer.objects.all()
    admin_notifications = AdminNotification.objects.all().order_by('-created_at')
    context = {
        'users_list': users,
        'system_stats': system_stats,
        'activity_logs': activity_logs,
        'tickets': tickets,
        'prefs': prefs,
        'db_table_counts': db_table_counts,
        'slow_queries_list': slow_queries_list,
        'readiness_scorecard': readiness_scorecard,
        'offers_list': offers_list,
        'admin_notifications': admin_notifications,
    }
    return render(request, 'expenses/admin_dashboard.html', context)


# Admin API: Toggle User Active Status
@csrf_exempt
@login_required
def admin_toggle_user(request):
    if not (request.user.is_staff or request.user.profile.role in ['super_admin', 'admin']):
        return JsonResponse({'success': False, 'error': 'Permission Denied'})
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        user = get_object_or_404(User, id=user_id)
        if user == request.user:
            return JsonResponse({'success': False, 'error': 'You cannot deactivate yourself.'})
        user.is_active = not user.is_active
        user.save()
        return JsonResponse({'success': True, 'is_active': user.is_active})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# Admin API: Change User Role
@csrf_exempt
@login_required
def admin_change_role(request):
    if not (request.user.is_staff or request.user.profile.role in ['super_admin', 'admin']):
        return JsonResponse({'success': False, 'error': 'Permission Denied'})
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        role = request.POST.get('role')
        if role not in ['super_admin', 'admin', 'support_staff', 'user']:
            return JsonResponse({'success': False, 'error': 'Invalid role choice.'})
        profile = get_object_or_404(Profile, user_id=user_id)
        profile.role = role
        profile.save()
        # Synchronize Django is_staff flag for convenience
        user = profile.user
        if role in ['super_admin', 'admin', 'support_staff']:
            user.is_staff = True
        else:
            user.is_staff = False
        user.save()
        return JsonResponse({'success': True, 'role': profile.role})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# Admin API: Change User Subscription Tier
@csrf_exempt
@login_required
def admin_change_subscription(request):
    if not (request.user.is_staff or request.user.profile.role in ['super_admin', 'admin']):
        return JsonResponse({'success': False, 'error': 'Permission Denied'})
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        tier = request.POST.get('tier')
        if tier not in ['free', 'premium', 'premium_ai', 'business']:
            return JsonResponse({'success': False, 'error': 'Invalid subscription tier.'})
        profile = get_object_or_404(Profile, user_id=user_id)
        profile.subscription_tier = tier
        profile.save()
        return JsonResponse({'success': True, 'subscription_tier': profile.subscription_tier})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# Admin API: Resolve Support Ticket
@csrf_exempt
@login_required
def admin_resolve_ticket(request):
    if not (request.user.is_staff or request.user.profile.role in ['super_admin', 'admin', 'support_staff']):
        return JsonResponse({'success': False, 'error': 'Permission Denied'})
    if request.method == 'POST':
        ticket_id = request.POST.get('ticket_id')
        ticket = get_object_or_404(SupportTicket, ticket_id=ticket_id)
        ticket.status = 'resolved'
        ticket.save()
        AdminNotification.objects.create(
            event_type='support_ticket',
            message=f"Support ticket #{ticket.ticket_id} ('{ticket.subject}') marked as RESOLVED by admin {request.user.username}"
        )
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# Admin API: Broadcast Notification to All Users
@csrf_exempt
@login_required
def admin_broadcast_notification(request):
    if not (request.user.is_staff or request.user.profile.role in ['super_admin', 'admin']):
        return JsonResponse({'success': False, 'error': 'Permission Denied'})
    if request.method == 'POST':
        message = request.POST.get('message')
        if not message:
            return JsonResponse({'success': False, 'error': 'Message cannot be empty.'})
        # Create notifications for all active users
        users = User.objects.filter(is_active=True)
        notifications = [
            Notification(user=u, message=f"📢 Announcement: {message}", status='unread')
            for u in users
        ]
        Notification.objects.bulk_create(notifications)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

# AJAX API: Voice Parsing
@csrf_exempt
@login_required
def parse_voice(request):
    if request.method == 'POST':
        text = request.POST.get('text', '')
        amount, category, description = parse_expense_text(text)
        return JsonResponse({
            'success': True,
            'amount': amount,
            'category': category,
            'description': description
        })
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

# AJAX API: Chatbot Query
@csrf_exempt
@login_required
def chatbot_query(request):
    if request.method == 'POST':
        query = request.POST.get('query', '')
        response_text = get_chatbot_response(request.user, query)
        return JsonResponse({
            'success': True,
            'response': response_text
        })
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

# AJAX API: Add Expense
@csrf_exempt
@login_required
def add_expense_ajax(request):
    if request.method == 'POST':
        category = request.POST.get('category')
        description = request.POST.get('description')
        amount = request.POST.get('amount')
        expense_date_str = request.POST.get('expense_date') or date.today().strftime('%Y-%m-%d')
        
        try:
            from datetime import datetime
            parsed_date = datetime.strptime(expense_date_str, '%Y-%m-%d').date()
            expense = Expense.objects.create(
                user=request.user,
                category=category,
                description=description,
                amount=Decimal(amount),
                expense_date=parsed_date
            )
            UserActivityLog.objects.create(
                user=request.user,
                action=f"Added Expense: {expense.amount} under '{expense.category}' ({expense.description})"
            )
            AdminNotification.objects.create(
                event_type='expense_creation',
                message=f"User {request.user.username} created expense of {expense.amount} INR under category '{expense.category}'"
            )
            return JsonResponse({
                'success': True,
                'expense_id': expense.expense_id,
                'category': expense.category,
                'description': expense.description,
                'amount': float(expense.amount),
                'expense_date': expense.expense_date.strftime('%Y-%m-%d')
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

# AJAX API: Edit Expense
@csrf_exempt
@login_required
def edit_expense_ajax(request):
    if request.method == 'POST':
        expense_id = request.POST.get('expense_id')
        if not expense_id or not str(expense_id).isdigit():
            return JsonResponse({'success': False, 'error': 'Invalid expense ID.'})
        expense = get_object_or_404(Expense, expense_id=expense_id, user=request.user)
        
        category = request.POST.get('category')
        description = request.POST.get('description')
        amount = request.POST.get('amount')
        expense_date_str = request.POST.get('expense_date')
        
        try:
            if category: expense.category = category
            if description: expense.description = description
            if amount: expense.amount = Decimal(amount)
            if expense_date_str:
                from datetime import datetime
                expense.expense_date = datetime.strptime(expense_date_str, '%Y-%m-%d').date()
            expense.save()
            UserActivityLog.objects.create(
                user=request.user,
                action=f"Edited Expense: {expense.amount} under '{expense.category}' ({expense.description})"
            )
            
            return JsonResponse({
                'success': True,
                'expense_id': expense.expense_id,
                'category': expense.category,
                'description': expense.description,
                'amount': float(expense.amount),
                'expense_date': expense.expense_date.strftime('%Y-%m-%d')
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

# AJAX API: Delete Expense
@csrf_exempt
@login_required
def delete_expense_ajax(request):
    if request.method == 'POST':
        expense_id = request.POST.get('expense_id')
        if not expense_id or not str(expense_id).isdigit():
            return JsonResponse({'success': False, 'error': 'Invalid expense ID.'})
        expense = get_object_or_404(Expense, expense_id=expense_id, user=request.user)
        try:
            UserActivityLog.objects.create(
                user=request.user,
                action=f"Deleted Expense: {expense.amount} under '{expense.category}' ({expense.description})"
            )
            AdminNotification.objects.create(
                event_type='expense_deletion',
                message=f"User {request.user.username} deleted expense of {expense.amount} INR under category '{expense.category}'"
            )
            expense.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

# Export: CSV Export View
@login_required
def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="smartspend_expenses_{date.today().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Expense ID', 'Category', 'Description', 'Amount', 'Date'])
    
    expenses = Expense.objects.filter(user=request.user)
    for expense in expenses:
        writer.writerow([
            expense.expense_id,
            expense.category,
            expense.description,
            expense.amount,
            expense.expense_date
        ])
        
    return response

# Export: PDF Report Export View using Reportlab
@login_required
def export_pdf(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.subscription_tier == 'free':
        return HttpResponse("🔒 Premium Feature: Please upgrade your subscription to download PDF reports.", status=403)
        
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="smartspend_expenses_{date.today().strftime("%Y%m%d")}.pdf"'
    
    # Setup document
    doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = []
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#6366f1'),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=20
    )
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.white,
        fontName='Helvetica-Bold'
    )
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#1e293b')
    )
    
    story.append(Paragraph("SmartSpend Monthly Financial Report", title_style))
    story.append(Paragraph(f"Generated for {request.user.username} | Date: {date.today().strftime('%d %B, %Y')}", subtitle_style))
    story.append(Spacer(1, 10))
    
    # Expenses Table
    expenses = Expense.objects.filter(user=request.user)
    data = [[
        Paragraph('Date', header_style), 
        Paragraph('Category', header_style), 
        Paragraph('Description', header_style), 
        Paragraph('Amount', header_style)
    ]]
    
    total = Decimal(0.0)
    for exp in expenses:
        data.append([
            Paragraph(exp.expense_date.strftime('%Y-%m-%d'), cell_style),
            Paragraph(exp.category, cell_style),
            Paragraph(exp.description, cell_style),
            Paragraph(f"{exp.amount:.2f}", cell_style)
        ])
        total += exp.amount
        
    # Total row
    total_label_style = ParagraphStyle('TotalLabel', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor('#1e293b'))
    data.append([
        Paragraph('Total Expenses', total_label_style),
        Paragraph('', total_label_style),
        Paragraph('', total_label_style),
        Paragraph(f"{total:.2f}", total_label_style)
    ])
    
    # Set columns: widths must sum up to 540 (printable letter size width is 612 - 72 = 540)
    t = Table(data, colWidths=[80, 100, 260, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#6366f1')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-2), 0.5, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f1f5f9')),
        ('LINEABOVE', (0,-1), (-1,-1), 1.5, colors.HexColor('#6366f1')),
    ]))
    
    story.append(t)
    doc.build(story)
    
    return response

# SEND WHATSAPP MESSAGE USING TWILIO
@staff_member_required
@csrf_exempt
@csrf_exempt
def send_whatsapp_to_user(request):

    if request.method == "POST":

        username = request.POST.get("username")
        phone = request.POST.get("phone")
        message = request.POST.get("message")

        print("USERNAME:", username)
        print("PHONE:", phone)
        print("MESSAGE:", message)

        try:

            sid = send_whatsapp_message(
                phone,
                message
            )

            return JsonResponse({
                "success": True,
                "sid": sid
            })

        except Exception as e:

            print("ERROR:", str(e))

            return JsonResponse({
                "success": False,
                "error": str(e)
            })

    return JsonResponse({
        "success": False,
        "error": "Invalid Request"
    })    

# AJAX API: Edit Budget
@csrf_exempt
@login_required
def edit_budget_ajax(request):
    if request.method == 'POST':
        budget_id = request.POST.get('budget_id')
        if not budget_id or not str(budget_id).isdigit():
            return JsonResponse({'success': False, 'error': 'Invalid budget ID.'})
        budget = get_object_or_404(Budget, budget_id=budget_id, user=request.user)
        limit_amount = request.POST.get('limit_amount')
        try:
            budget.limit_amount = Decimal(limit_amount)
            budget.save()
            UserActivityLog.objects.create(
                user=request.user,
                action=f"Updated Budget: {budget.category} limit set to {budget.limit_amount}"
            )
            AdminNotification.objects.create(
                event_type='budget_change',
                message=f"User {request.user.username} updated budget for '{budget.category}' to {budget.limit_amount} INR"
            )
            return JsonResponse({
                'success': True,
                'budget_id': budget.budget_id,
                'category': budget.category,
                'limit_amount': float(budget.limit_amount),
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

# AJAX API: Delete Budget
@csrf_exempt
@login_required
def delete_budget_ajax(request):
    if request.method == 'POST':
        budget_id = request.POST.get('budget_id')
        if not budget_id or not str(budget_id).isdigit():
            return JsonResponse({'success': False, 'error': 'Invalid budget ID.'})
        budget = get_object_or_404(Budget, budget_id=budget_id, user=request.user)
        try:
            UserActivityLog.objects.create(
                user=request.user,
                action=f"Deleted Budget: {budget.category}"
            )
            AdminNotification.objects.create(
                event_type='budget_change',
                message=f"User {request.user.username} deleted budget for '{budget.category}'"
            )
            budget.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

# AJAX API: WhatsApp Webhook (Twilio Integration)
@csrf_exempt
def whatsapp_webhook(request):
    # Log incoming request to a local debug file
    with open('webhook_debug.log', 'a', encoding='utf-8') as f:
        f.write(f"\n--- Webhook received at {datetime.now()} ---\n")
        f.write(f"Method: {request.method}\n")
        f.write(f"Headers: {dict(request.headers)}\n")
        f.write(f"POST params: {dict(request.POST)}\n")

    if request.method == 'POST':
        # 1. Twilio Signature Validation in Production
        from twilio.request_validator import RequestValidator
        import sys
        twilio_signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
        is_testing = 'test' in sys.argv or getattr(settings, 'TESTING', False)
        
        if not settings.DEBUG and not is_testing:
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
            validator = RequestValidator(auth_token)
            url = request.build_absolute_uri()
            # Handle HTTPS reverse proxy
            if request.headers.get('X-Forwarded-Proto') == 'https' and url.startswith('http:'):
                url = url.replace('http:', 'https:', 1)
            
            if not twilio_signature or not validator.validate(url, request.POST, twilio_signature):
                return HttpResponse("Invalid Twilio Signature", status=403)

        from_number = request.POST.get('From', '') # e.g. "whatsapp:+919944550063"
        body = request.POST.get('Body', '').strip()
        
        # Extract pure phone number (remove whatsapp: prefix)
        incoming_number = from_number.replace('whatsapp:', '').strip()
        
        # Admin authentication checking settings or profile
        admin_number = getattr(settings, 'ADMIN_WHATSAPP_NUMBER', '+919944550063').replace('whatsapp:', '').strip()
        
        is_authorized = (incoming_number == admin_number)
        
        admin_user = None
        if is_authorized:
            admin_user = User.objects.filter(is_superuser=True).first()
        else:
            # Fallback: check if there's any superuser with this whatsapp number in profile
            admin_user = User.objects.filter(is_superuser=True, profile__whatsapp_number__icontains=incoming_number).first()
            if admin_user:
                is_authorized = True

        if not is_authorized:
            response_xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Response>'
                '<Message>Unauthorized access</Message>'
                '</Response>'
            )
            return HttpResponse(response_xml, content_type='application/xml')

        # Command parsing
        body_upper = body.upper().strip()
        reply_message = ""
        
        if body_upper == 'SHOW USERS' or body_upper == 'USERS':
            total_users = User.objects.count()
            users = User.objects.all().order_by('id')
            user_list = "\n".join([f"• [{u.id}] *{u.username}* ({u.email or 'No email'}) - {u.profile.subscription_tier.upper()}" for u in users[:20]])
            if total_users > 20:
                user_list += "\n... and more."
            reply_message = f"👥 *SmartSpend Users* (Total: {total_users}):\n{user_list}"
            
        elif body_upper.startswith('DELETE USER '):
            # Format: DELETE USER <id>
            parts = body.strip().split()
            if len(parts) < 3:
                reply_message = "⚠️ Format: *DELETE USER <id>*"
            else:
                try:
                    uid = int(parts[2])
                    user_to_delete = User.objects.filter(id=uid).first()
                    if not user_to_delete:
                        reply_message = f"❌ User ID {uid} not found."
                    elif user_to_delete.is_superuser:
                        reply_message = "❌ Cannot delete a superuser/admin via WhatsApp."
                    else:
                        username = user_to_delete.username
                        user_to_delete.delete()
                        reply_message = f"✅ User *{username}* (ID: {uid}) was deleted from the platform."
                except ValueError:
                    reply_message = "❌ Invalid User ID format. ID must be an integer."
                    
        elif body_upper == 'VIEW REPORT':
            today = date.today()
            expenses_today = Expense.objects.filter(expense_date=today)
            total_today = expenses_today.aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
            count_today = expenses_today.count()
            
            lines = [
                f"📅 *Daily Platform Report ({today.strftime('%Y-%m-%d')})*:",
                f"• Total Logged Today: ₹{total_today:.2f}",
                f"• Total Transactions Today: {count_today}",
                "",
                "📝 *Recent Items today*:"
            ]
            for exp in expenses_today[:10]:
                lines.append(f"- *{exp.user.username}*: ₹{exp.amount:.2f} | {exp.category} ({exp.description})")
            if count_today > 10:
                lines.append("... and more.")
            reply_message = "\n".join(lines)
            
        elif body_upper == 'TOTAL EXPENSES':
            total_amount = Expense.objects.aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
            total_count = Expense.objects.count()
            reply_message = (
                f"💰 *Platform-Wide Expense Totals*:\n"
                f"• Total Amount Spent: ₹{total_amount:.2f}\n"
                f"• Total Transactions Logged: {total_count}"
            )
            
        elif body_upper.startswith('SEND ALERT '):
            # Format: SEND ALERT <message>
            # Split off the first two tokens ('SEND', 'ALERT')
            parts = body.split(maxsplit=2)
            if len(parts) < 3:
                reply_message = "⚠️ Format: *SEND ALERT <message>*"
            else:
                alert_msg = parts[2].strip()
                users = User.objects.filter(is_active=True)
                notifications = [
                    Notification(user=u, message=f"📢 Announcement: {alert_msg}", status='unread')
                    for u in users
                ]
                Notification.objects.bulk_create(notifications)
                reply_message = f"📢 Broadcasted alert to {users.count()} active users:\n\"{alert_msg}\""
                
        elif body_upper == 'SERVER STATUS' or body_upper == 'STATUS':
            import os
            db_size_mb = 0.0
            try:
                db_path = settings.DATABASES['default']['NAME']
                if os.path.exists(db_path):
                    db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
            except Exception:
                pass
                
            reply_message = (
                f"🖥️ *SmartSpend Server Status*:\n"
                f"• Server Health: 🟢 HEALTHY / ONLINE\n"
                f"• DB Engine: {settings.DATABASES['default']['ENGINE'].split('.')[-1]}\n"
                f"• DB File Size: {db_size_mb:.2f} MB\n"
                f"• Active User Count: {User.objects.filter(is_active=True).count()}\n"
                f"• Total Log Entries: {UserActivityLog.objects.count()}"
            )
            
        elif body_upper == 'TOP SPENDERS':
            top_users = User.objects.annotate(total_spent=Sum('expenses__amount')).order_by('-total_spent')[:5]
            lines = ["🏆 *Top 5 Platform Spenders*:"]
            for i, u in enumerate(top_users, 1):
                spent = u.total_spent or Decimal(0.0)
                lines.append(f"{i}. *{u.username}* - ₹{spent:.2f} ({u.expenses.count()} txs)")
            reply_message = "\n".join(lines)
            
        elif body_upper == 'BUDGET ALERTS':
            today = date.today()
            start_of_month = date(today.year, today.month, 1)
            budgets = Budget.objects.all()
            lines = ["🚨 *Active Budget Exceeded Alerts*:"]
            breach_count = 0
            for b in budgets:
                spent = Expense.objects.filter(user=b.user, category=b.category, expense_date__gte=start_of_month).aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
                if spent > b.limit_amount:
                    breach_count += 1
                    lines.append(f"• *{b.user.username}*: {b.category} (Spent ₹{spent:.2f} / Limit ₹{b.limit_amount:.2f})")
            
            if breach_count == 0:
                reply_message = "✅ All user budgets are currently in good standing."
            else:
                reply_message = "\n".join(lines)
                
        elif body_upper == 'EXPORT CSV':
            # Generate export CSV link
            csv_url = request.build_absolute_uri('/export/csv/')
            reply_message = (
                f"📥 *Export Platform Expenses*:\n"
                f"Click the link below to download the CSV database backup:\n"
                f"{csv_url}"
            )
            
        elif body_upper.startswith('ADD '):
            # Keep existing ADD command helper for convenience
            # Format: ADD <username> <amount> <category> <description...>
            parts = body.split(maxsplit=4)
            if len(parts) < 5:
                reply_message = "⚠️ Format: *ADD <username> <amount> <category> <description...>*"
            else:
                target_user = User.objects.filter(username__iexact=parts[1]).first()
                if not target_user:
                    reply_message = f"❌ User '{parts[1]}' not found."
                else:
                    try:
                        amt = Decimal(parts[2])
                        cat = parts[3].capitalize()
                        desc = parts[4]
                        valid_cats = [choice[0] for choice in CATEGORY_CHOICES]
                        if cat not in valid_cats:
                            reply_message = f"❌ Invalid category '{cat}'. Choices: {', '.join(valid_cats)}"
                        else:
                            exp = Expense.objects.create(
                                user=target_user,
                                amount=amt,
                                category=cat,
                                description=desc,
                                expense_date=date.today()
                            )
                            reply_message = f"✅ Added expense of ₹{amt:.2f} under '{cat}' for {target_user.username}. ID: {exp.expense_id}"
                    except Exception as e:
                        reply_message = f"❌ Error adding expense: {str(e)}"
                        
        elif body_upper.startswith('DELETE '):
            # Keep existing delete expense command
            parts = body.split()
            if len(parts) < 2:
                reply_message = "⚠️ Format: *DELETE <expense_id>*"
            else:
                try:
                    exp_id = int(parts[1])
                    exp = Expense.objects.filter(expense_id=exp_id).first()
                    if not exp:
                        reply_message = f"❌ Expense ID {exp_id} not found."
                    else:
                        owner = exp.user.username
                        amt = exp.amount
                        exp.delete()
                        reply_message = f"✅ Deleted expense ID {exp_id} (₹{amt:.2f} for {owner})."
                except Exception as e:
                    reply_message = f"❌ Error: {str(e)}"
                    
        elif body_upper.startswith('BUDGETS '):
            # Keep existing view/set budgets helper
            parts = body.split()
            if len(parts) < 2:
                reply_message = "⚠️ Format:\n• *BUDGETS <username>*\n• *BUDGETS <username> <category> <limit>*"
            elif len(parts) < 4:
                target_user = User.objects.filter(username__iexact=parts[1]).first()
                if not target_user:
                    reply_message = f"❌ User '{parts[1]}' not found."
                else:
                    user_budgets = Budget.objects.filter(user=target_user)
                    if not user_budgets.exists():
                        reply_message = f"📋 No budgets set for {target_user.username}."
                    else:
                        lines = [f"📋 *Budgets for {target_user.username}*:"]
                        for b in user_budgets:
                            lines.append(f"• {b.category}: ₹{b.limit_amount:.2f}")
                        reply_message = "\n".join(lines)
            else:
                target_user = User.objects.filter(username__iexact=parts[1]).first()
                if not target_user:
                    reply_message = f"❌ User '{parts[1]}' not found."
                else:
                    try:
                        cat = parts[2].capitalize()
                        limit = Decimal(parts[3])
                        valid_cats = [choice[0] for choice in CATEGORY_CHOICES]
                        if cat not in valid_cats:
                            reply_message = f"❌ Invalid category '{cat}'."
                        else:
                            budget, created = Budget.objects.update_or_create(
                                user=target_user,
                                category=cat,
                                defaults={'limit_amount': limit}
                            )
                            reply_message = f"✅ Budget updated: {target_user.username} - {cat} limit set to ₹{limit:.2f}."
                    except Exception as e:
                        reply_message = f"❌ Error updating budget: {str(e)}"
                        
        elif body_upper == 'HELP':
            reply_message = (
                f"🤖 *SmartSpend Admin WhatsApp Controller*:\n\n"
                f"• *SHOW USERS*: List platform users.\n"
                f"• *DELETE USER <id>*: Delete user account by ID.\n"
                f"• *VIEW REPORT*: Today's logged expenses report.\n"
                f"• *TOTAL EXPENSES*: Platform-wide spending summary.\n"
                f"• *SEND ALERT <msg>*: Broadcast announcement notification.\n"
                f"• *SERVER STATUS*: Server/database analytics.\n"
                f"• *TOP SPENDERS*: View top 5 spenders.\n"
                f"• *BUDGET ALERTS*: List active budget breaches.\n"
                f"• *EXPORT CSV*: Get platform CSV report link.\n"
                f"• *HELP*: List admin options."
            )
        else:
            reply_message = f"❓ Unknown command: '{body}'. Type *HELP* to see list of valid admin commands."
            
        import html
        response_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            f'<Message>{html.escape(reply_message)}</Message>'
            '</Response>'
        )
        return HttpResponse(response_xml, content_type='application/xml')
        
    return HttpResponse("Invalid request method.", status=400)

def service_worker(request):
    import os
    from django.conf import settings
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'js', 'service-worker.js')
    with open(sw_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return HttpResponse(content, content_type='application/javascript')

# ─── Helper: generate unique referral code ───────────────────────────────────
def _generate_referral_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if not Profile.objects.filter(referral_code=code).exists():
            return code

# ─── Helper: update daily login streak ───────────────────────────────────────
def _update_streak(profile):
    today = date.today()
    if profile.last_active_date:
        delta = (today - profile.last_active_date).days
        if delta == 1:
            profile.streak_count += 1
        elif delta > 1:
            profile.streak_count = 1
        # If delta == 0, same day login — no change
    else:
        profile.streak_count = 1
    profile.last_active_date = today
    profile.save(update_fields=['streak_count', 'last_active_date'])

# ─── AJAX: Parse Bank / UPI / Wallet SMS ─────────────────────────────────────
@csrf_exempt
@login_required
def parse_sms_ajax(request):
    if request.method == 'POST':
        sms_text = request.POST.get('sms_text', '').strip()
        if not sms_text:
            return JsonResponse({'success': False, 'error': 'SMS text is required.'})
        amount, category, description, payment_mode = parse_bank_sms(sms_text)
        return JsonResponse({
            'success': True,
            'amount': amount,
            'category': category,
            'description': description,
            'payment_mode': payment_mode,
        })
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

# ─── Pricing Page ─────────────────────────────────────────────────────────────
def pricing_view(request):
    return render(request, 'expenses/pricing.html')

# ─── Subscription Upgrade (simulated) ────────────────────────────────────────
@login_required
def upgrade_subscription(request):
    if request.method == 'POST':
        tier = request.POST.get('tier', 'free')
        if tier in ['free', 'pro', 'business', 'enterprise']:
            profile, _ = Profile.objects.get_or_create(user=request.user)
            profile.subscription_tier = tier
            if tier != 'free':
                profile.subscription_end_date = date.today() + timedelta(days=30)
            else:
                profile.subscription_end_date = None
            profile.save(update_fields=['subscription_tier', 'subscription_end_date'])
            Notification.objects.create(
                user=request.user,
                message=f"Your subscription has been upgraded to {tier.capitalize()}. Enjoy the premium features!"
            )
            AdminNotification.objects.create(
                event_type='subscription_upgrade',
                message=f"User {request.user.username} upgraded subscription to '{tier}'"
            )
            return JsonResponse({'success': True, 'tier': tier})
        return JsonResponse({'success': False, 'error': 'Invalid tier selection.'})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

# ─── Checkout & Billing Simulation ───────────────────────────────────────────
@login_required
def checkout_view(request):
    # Ensure default coupons exist
    from expenses.models import Coupon, SubscriptionPayment
    from django.utils.timezone import now
    
    if not Coupon.objects.exists():
        Coupon.objects.create(code="SAVE10", discount_percent=10, expiry_date=date(2030, 12, 31), is_active=True)
        Coupon.objects.create(code="FINTECH30", discount_percent=30, expiry_date=date(2030, 12, 31), is_active=True)
        Coupon.objects.create(code="WELCOME50", discount_percent=50, expiry_date=date(2030, 12, 31), is_active=True)

    if request.method == 'POST':
        plan = request.POST.get('plan')
        billing_cycle = request.POST.get('billing_cycle', 'monthly') # 'monthly' or 'annual'
        coupon_code = request.POST.get('coupon_code', '').strip().upper()
        amount_str = request.POST.get('amount')
        
        valid_plans = ['pro', 'business', 'enterprise']
        if plan not in valid_plans:
            return render(request, 'expenses/checkout.html', {
                'error': 'Invalid plan selected.',
                'plan': plan,
                'billing_cycle': billing_cycle
            })
            
        try:
            amount = Decimal(amount_str)
        except (ValueError, TypeError):
            amount = Decimal('0.00')
            
        # Validate coupon if provided
        coupon = None
        if coupon_code:
            coupon = Coupon.objects.filter(code=coupon_code, is_active=True, expiry_date__gte=date.today()).first()
            if not coupon:
                return render(request, 'expenses/checkout.html', {
                    'error': 'Invalid or expired discount coupon.',
                    'plan': plan,
                    'billing_cycle': billing_cycle
                })
        
        # Payment simulation success! Upgrade profile
        profile, _ = Profile.objects.get_or_create(user=request.user)
        profile.subscription_tier = plan
        
        days = 365 if billing_cycle == 'annual' else 30
        profile.subscription_end_date = date.today() + timedelta(days=days)
        profile.save()
        
        # Log subscription payment
        payment = SubscriptionPayment.objects.create(
            user=request.user,
            plan=plan,
            amount=amount,
            billing_cycle=billing_cycle,
            coupon_used=coupon
        )
        
        # Log coupon redemption
        if coupon:
            CouponRedemption.objects.create(
                user=request.user,
                coupon=coupon
            )
            
        # Synchronously generate the PDF invoice for instant access
        try:
            from expenses.tasks import generate_pdf_invoice_task
            generate_pdf_invoice_task(payment.id)
        except Exception as e:
            print("Invoice generation error:", str(e))
        
        # Send Notification
        Notification.objects.create(
            user=request.user,
            message=f"🎉 Congratulations! Your account has been upgraded to {plan.capitalize()} Plan ({billing_cycle}). Enjoy your advanced features!"
        )
        
        # Log to activity log
        UserActivityLog.objects.create(
            user=request.user,
            action=f"Upgraded subscription to {plan} ({billing_cycle}) for {amount} INR"
        )
        
        # Log Admin Notifications
        AdminNotification.objects.create(
            event_type='payment',
            message=f"User {request.user.username} paid {amount} INR for '{plan}' plan ({billing_cycle})"
        )
        AdminNotification.objects.create(
            event_type='subscription_upgrade',
            message=f"User {request.user.username} upgraded to subscription '{plan}'"
        )
        
        return render(request, 'expenses/checkout.html', {
            'success': True,
            'plan': plan,
            'billing_cycle': billing_cycle,
            'amount': amount
        })

    # GET request
    plan = request.GET.get('plan', 'pro')
    billing_cycle = request.GET.get('billing_cycle', 'monthly')
    
    # Calculate initial prices
    prices = {
        'pro': {'monthly': 9.99, 'annual': 99.90},
        'business': {'monthly': 19.99, 'annual': 199.90},
        'enterprise': {'monthly': 49.99, 'annual': 499.90}
    }
    
    initial_price = prices.get(plan, prices['pro']).get(billing_cycle, 9.99)
    
    context = {
        'plan': plan,
        'billing_cycle': billing_cycle,
        'initial_price': initial_price,
        'profile': request.user.profile if hasattr(request.user, 'profile') else None
    }
    return render(request, 'expenses/checkout.html', context)

@csrf_exempt
def validate_coupon_ajax(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            code = data.get('code', '').strip().upper()
        except Exception:
            code = request.POST.get('code', '').strip().upper()
            
        from expenses.models import Coupon
        coupon = Coupon.objects.filter(code=code, is_active=True, expiry_date__gte=date.today()).first()
        if coupon:
            return JsonResponse({'success': True, 'discount_percent': coupon.discount_percent})
        return JsonResponse({'success': False, 'error': 'Coupon is invalid, inactive, or expired.'})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# ─── Referral System ──────────────────────────────────────────────────────────
@login_required
def referral_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.referral_code:
        profile.referral_code = _generate_referral_code()
        profile.save(update_fields=['referral_code'])
    referral_count = Profile.objects.filter(referred_by=request.user).count()
    context = {
        'profile': profile,
        'referral_count': referral_count,
        'referral_link': request.build_absolute_uri(f"/register/?ref={profile.referral_code}"),
    }
    return render(request, 'expenses/achievements.html', context)

# ─── Achievements / Gamification Dashboard ────────────────────────────────────
@login_required
def achievements_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not profile.referral_code:
        profile.referral_code = _generate_referral_code()
        profile.save(update_fields=['referral_code'])

    _update_streak(profile)

    # Determine unlocked achievements
    expense_count = Expense.objects.filter(user=request.user).count()
    achievements_list = json.loads(profile.achievements) if profile.achievements else []

    badge_rules = [
        ('first_expense', 'First Expense', expense_count >= 1),
        ('expense_10', '10 Expenses Logged', expense_count >= 10),
        ('expense_50', '50 Expenses Logged', expense_count >= 50),
        ('streak_3', '3-Day Streak', profile.streak_count >= 3),
        ('streak_7', 'Week Warrior', profile.streak_count >= 7),
        ('streak_30', 'Monthly Master', profile.streak_count >= 30),
        ('premium_user', 'Premium Member', profile.subscription_tier != 'free'),
    ]
    new_badges = []
    for badge_id, badge_name, condition in badge_rules:
        if condition and badge_id not in achievements_list:
            achievements_list.append(badge_id)
            new_badges.append(badge_name)
    if new_badges:
        profile.achievements = json.dumps(achievements_list)
        profile.save(update_fields=['achievements'])
        for badge in new_badges:
            Notification.objects.create(user=request.user, message=f"Achievement Unlocked: {badge}!")

    challenges = SavingsChallenge.objects.filter(user=request.user)
    referral_count = Profile.objects.filter(referred_by=request.user).count()

    context = {
        'profile': profile,
        'achievements_list': achievements_list,
        'badge_rules': badge_rules,
        'challenges': challenges,
        'streak': profile.streak_count,
        'referral_count': referral_count,
        'referral_link': request.build_absolute_uri(f"/register/?ref={profile.referral_code}"),
        'prefs': get_user_preferences(request),
    }
    return render(request, 'expenses/achievements.html', context)

# ─── Savings Challenge: Create ────────────────────────────────────────────────
@login_required
def create_challenge(request):
    if request.method == 'POST':
        title = request.POST.get('title', 'My Savings Goal')
        target = request.POST.get('target_amount', 0)
        end_date_str = request.POST.get('end_date', '')
        try:
            challenge = SavingsChallenge.objects.create(
                user=request.user,
                title=title,
                target_amount=Decimal(target),
                current_amount=Decimal('0.00'),
                end_date=datetime.strptime(end_date_str, '%Y-%m-%d').date()
            )
            return JsonResponse({'success': True, 'id': challenge.challenge_id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid method.'})

# ─── Notifications: Mark All Read ─────────────────────────────────────────────
@login_required
def mark_notifications_read(request):
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, status='unread').update(status='read')
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

# ─── About Page ───────────────────────────────────────────────────────────────
def about_view(request):
    return render(request, 'expenses/about.html')

# ─── Features Page ────────────────────────────────────────────────────────────
def features_view(request):
    return render(request, 'expenses/features.html')

# ─── Contact Page ─────────────────────────────────────────────────────────────
def contact_view(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        message = request.POST.get('message', '').strip()
        # Log the contact form submission as a system activity
        UserActivityLog.objects.create(
            user=None,
            action=f"Contact form: {name} ({email}) - {message[:80]}"
        )
        return JsonResponse({'success': True, 'message': 'Thank you! We will get back to you soon.'})
    return render(request, 'expenses/contact.html')


# ─── Team Management (Business Tier) ─────────────────────────────────────────
@login_required
def team_management(request):
    from expenses.models import TeamMembership, TeamExpenseApproval
    prefs = get_user_preferences(request)
    profile = request.user.profile
    
    owned_team = Team.objects.filter(owner=request.user).first()
    member_team = Team.objects.filter(members=request.user).first()
    
    team = owned_team or member_team
    
    if not team and profile.subscription_tier in ['business', 'enterprise']:
        team = Team.objects.create(owner=request.user, name=f"{request.user.username}'s Business Workspace")
        
    is_business_or_member = (team is not None)
    
    team_memberships = []
    pending_approvals = []
    team_expenses = []
    user_role = 'employee'
    
    if team:
        membership = team.memberships.filter(user=request.user).first()
        if membership:
            user_role = membership.role
        elif team.owner == request.user:
            user_role = 'owner'
            
        team_memberships = team.memberships.select_related('user').order_by('role')
        
        member_ids = team.members.values_list('id', flat=True)
        team_expenses = Expense.objects.filter(user_id__in=member_ids).select_related('user').order_by('-expense_date')[:25]
        
        pending_approvals = team.expense_approvals.filter(status='pending').select_related('submitted_by')

    context = {
        'prefs': prefs,
        'profile': profile,
        'is_business': is_business_or_member,
        'team': team,
        'team_memberships': team_memberships,
        'pending_approvals': pending_approvals,
        'team_expenses': team_expenses,
        'user_role': user_role,
    }
    return render(request, 'expenses/team.html', context)


# ─── Add Team Member AJAX ─────────────────────────────────────────────────────
@csrf_exempt
@login_required
def add_team_member_ajax(request):
    if request.method == 'POST':
        profile = request.user.profile
        if profile.subscription_tier != 'business':
            return JsonResponse({'success': False, 'error': 'Only Business plan subscribers can manage teams.'})
        
        username = request.POST.get('username', '').strip()
        team = get_object_or_404(Team, owner=request.user)
        
        try:
            member_user = User.objects.get(username=username)
            if member_user == request.user:
                return JsonResponse({'success': False, 'error': 'You are already the owner of this team.'})
            if team.members.filter(id=member_user.id).exists():
                return JsonResponse({'success': False, 'error': f"{username} is already a member of your team."})
            team.members.add(member_user)
            UserActivityLog.objects.create(
                user=request.user,
                action=f"Added team member: {username} to team '{team.name}'"
            )
            AdminNotification.objects.create(
                event_type='team_invite',
                message=f"User {request.user.username} added teammate {member_user.username} to team '{team.name}'"
            )
            return JsonResponse({
                'success': True,
                'member_id': member_user.id,
                'username': member_user.username,
                'email': member_user.email
            })
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': f"User '{username}' does not exist."})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# ─── Remove Team Member AJAX ──────────────────────────────────────────────────
@csrf_exempt
@login_required
def remove_team_member_ajax(request):
    if request.method == 'POST':
        profile = request.user.profile
        if profile.subscription_tier != 'business':
            return JsonResponse({'success': False, 'error': 'Only Business plan subscribers can manage teams.'})
            
        member_id = request.POST.get('member_id')
        team = get_object_or_404(Team, owner=request.user)
        
        try:
            member_user = User.objects.get(id=member_id)
            team.members.remove(member_user)
            UserActivityLog.objects.create(
                user=request.user,
                action=f"Removed team member: {member_user.username} from team '{team.name}'"
            )
            return JsonResponse({'success': True})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Member not found.'})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# ─── Affiliate Financial Offers ───────────────────────────────────────────────
@login_required
def affiliate_offers(request):
    # Ensure default offers exist
    if not Offer.objects.exists():
        Offer.objects.create(
            title="SmartSpend Platinum Credit Card",
            description="Get up to 5% cashback on all category expenses logged in SmartSpend. Zero annual fees for the first year, plus ₹1,500 welcome bonus on activation.",
            category="Credit Cards",
            affiliate_link="https://www.hdfcbank.com/personal/pay/cards/credit-cards/moneyback-plus",
            is_active=True,
            payout_amount=Decimal("20.00")
        )
        Offer.objects.create(
            title="High-Yield Savings & SIP Funds",
            description="Earn up to 7.2% p.a. interest on savings or auto-invest your spare change directly into zero-commission mutual funds using partner SIP plans.",
            category="Investments",
            affiliate_link="https://www.groww.in",
            is_active=True,
            payout_amount=Decimal("15.00")
        )
        Offer.objects.create(
            title="Instant Life & Health Cover",
            description="Secure your family's future with partner term life cover starting from ₹499/mo. 100% paperless medical checks and instant coverage generation.",
            category="Insurance",
            affiliate_link="https://www.policybazaar.com",
            is_active=True,
            payout_amount=Decimal("30.00")
        )
        
    offers = Offer.objects.filter(is_active=True)
    # Increment impressions dynamically for each listed offer
    for offer in offers:
        offer.impressions = offer.impressions + 1
        offer.save(update_fields=['impressions'])
        
    prefs = get_user_preferences(request)
    return render(request, 'expenses/offers.html', {'offers': offers, 'prefs': prefs})

@login_required
def offer_redirect(request, offer_id):
    offer = get_object_or_404(Offer, offer_id=offer_id, is_active=True)
    # Log click
    OfferClick.objects.create(offer=offer, user=request.user)
    return redirect(offer.affiliate_link)

@csrf_exempt
def record_offer_conversion_api(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
        except Exception:
            data = request.POST
            
        click_id = data.get('click_id')
        revenue_str = data.get('revenue', '0.00')
        
        if not click_id:
            return JsonResponse({'success': False, 'error': 'Missing click_id.'}, status=400)
            
        try:
            click = OfferClick.objects.get(click_id=click_id)
            revenue = Decimal(revenue_str)
        except OfferClick.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Offer click not found.'}, status=404)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid revenue format.'}, status=400)
            
        conversion, created = OfferConversion.objects.get_or_create(click=click, defaults={'revenue': revenue})
        if not created:
            conversion.revenue = revenue
            conversion.save()
            
        # Log payment/commission events
        AdminNotification.objects.create(
            event_type='payment',
            message=f"Affiliate conversion logged for click #{click_id}. Revenue earned: {revenue} INR"
        )
        return JsonResponse({'success': True, 'conversion_id': conversion.conversion_id, 'created': created})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


# ─── Support Ticketing Page ───────────────────────────────────────────────────
@login_required
def support_page(request):
    prefs = get_user_preferences(request)
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        if form_type == 'ticket':
            subject = request.POST.get('subject', '').strip()
            message = request.POST.get('message', '').strip()
            if subject and message:
                ticket = SupportTicket.objects.create(
                    user=request.user,
                    subject=subject,
                    message=message
                )
                UserActivityLog.objects.create(
                    user=request.user,
                    action=f"Created support ticket #{ticket.ticket_id}: {subject}"
                )
                AdminNotification.objects.create(
                    event_type='support_ticket',
                    message=f"New support ticket #{ticket.ticket_id} created by user {request.user.username}: '{subject}'"
                )
                return redirect('support_page')
        elif form_type == 'feedback':
            feedback_type = request.POST.get('feedback_type', 'review')
            title = request.POST.get('title', '').strip()
            description = request.POST.get('description', '').strip()
            if title and description:
                from expenses.models import Feedback
                fb = Feedback.objects.create(
                    user=request.user,
                    feedback_type=feedback_type,
                    title=title,
                    description=description
                )
                UserActivityLog.objects.create(
                    user=request.user,
                    action=f"Submitted feedback: {fb.get_feedback_type_display()} - {title}"
                )
                return redirect('support_page')
            
    return render(request, 'expenses/support.html', {'prefs': prefs, 'tickets': tickets})



# ─── Sync Offline Expenses AJAX ───────────────────────────────────────────────
@csrf_exempt
@login_required
def sync_offline_expenses(request):
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            expenses_data = data.get('expenses', [])
            
            expense_objects = []
            for exp in expenses_data:
                category = exp.get('category')
                description = exp.get('description')
                amount = exp.get('amount')
                expense_date_str = exp.get('expense_date') or date.today().strftime('%Y-%m-%d')
                parsed_date = datetime.strptime(expense_date_str, '%Y-%m-%d').date()
                
                expense_objects.append(
                    Expense(
                        user=request.user,
                        category=category,
                        description=description,
                        amount=Decimal(amount),
                        expense_date=parsed_date
                    )
                )
                
            if expense_objects:
                Expense.objects.bulk_create(expense_objects)
                created_count = len(expense_objects)
                UserActivityLog.objects.create(
                    user=request.user,
                    action=f"Synchronized {created_count} offline expenses."
                )
            else:
                created_count = 0
                
            return JsonResponse({'success': True, 'count': created_count})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# ─── Business Team Change Role AJAX ──────────────────────────────────────────
@csrf_exempt
@login_required
def change_member_role_ajax(request):
    if request.method == 'POST':
        from expenses.models import TeamMembership
        member_id = request.POST.get('member_id')
        new_role = request.POST.get('role', 'employee')
        
        if new_role not in ['manager', 'employee']:
            return JsonResponse({'success': False, 'error': 'Invalid role choice.'})
            
        team = Team.objects.filter(owner=request.user).first()
        if not team:
            return JsonResponse({'success': False, 'error': 'Only the team owner can modify roles.'})
            
        membership = team.memberships.filter(user_id=member_id).first()
        if not membership:
            return JsonResponse({'success': False, 'error': 'Member not found in team.'})
            
        membership.role = new_role
        membership.save(update_fields=['role'])
        
        UserActivityLog.objects.create(
            user=request.user,
            action=f"Changed team member {membership.user.username} role to {new_role}"
        )
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# ─── Submit Team Expense AJAX ────────────────────────────────────────────────
@csrf_exempt
@login_required
def submit_team_expense_ajax(request):
    if request.method == 'POST':
        from expenses.models import TeamExpenseApproval
        team_id = request.POST.get('team_id')
        team = get_object_or_404(Team, pk=team_id)
        
        if not team.members.filter(id=request.user.id).exists() and team.owner != request.user:
            return JsonResponse({'success': False, 'error': 'You are not a member of this team.'})
            
        amount = request.POST.get('amount')
        category = request.POST.get('category', 'Other')
        description = request.POST.get('description', '')
        expense_date_str = request.POST.get('expense_date', '')
        
        try:
            expense_date = datetime.strptime(expense_date_str, '%Y-%m-%d').date()
            membership = team.memberships.filter(user=request.user).first()
            role = membership.role if membership else ('owner' if team.owner == request.user else 'employee')
            
            if role in ['owner', 'manager']:
                expense = Expense.objects.create(
                    user=request.user,
                    category=category,
                    description=description,
                    amount=Decimal(amount),
                    expense_date=expense_date
                )
                TeamExpenseApproval.objects.create(
                    team=team,
                    submitted_by=request.user,
                    category=category,
                    description=description,
                    amount=Decimal(amount),
                    expense_date=expense_date,
                    status='approved',
                    approved_by=request.user
                )
                UserActivityLog.objects.create(
                    user=request.user,
                    action=f"Created team expense directly (Auto-approved): {amount} under {category}"
                )
                return JsonResponse({'success': True, 'msg': 'Expense created directly (Auto-approved).'})
            else:
                approval = TeamExpenseApproval.objects.create(
                    team=team,
                    submitted_by=request.user,
                    category=category,
                    description=description,
                    amount=Decimal(amount),
                    expense_date=expense_date,
                    status='pending'
                )
                UserActivityLog.objects.create(
                    user=request.user,
                    action=f"Submitted pending team expense for approval: {amount} under {category}"
                )
                return JsonResponse({'success': True, 'msg': 'Expense submitted successfully for manager approval.'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# ─── Process Team Expense AJAX ───────────────────────────────────────────────
@csrf_exempt
@login_required
def process_team_expense_ajax(request):
    if request.method == 'POST':
        from expenses.models import TeamExpenseApproval
        approval_id = request.POST.get('approval_id')
        action = request.POST.get('action')
        
        approval = get_object_or_404(TeamExpenseApproval, pk=approval_id)
        team = approval.team
        
        membership = team.memberships.filter(user=request.user).first()
        role = membership.role if membership else ('owner' if team.owner == request.user else 'employee')
        
        if role not in ['owner', 'manager']:
            return JsonResponse({'success': False, 'error': 'Only owners or managers can approve/reject team expenses.'})
            
        if approval.status != 'pending':
            return JsonResponse({'success': False, 'error': 'This expense has already been processed.'})
            
        if action == 'approve':
            approval.status = 'approved'
            approval.approved_by = request.user
            approval.save()
            
            Expense.objects.create(
                user=approval.submitted_by,
                category=approval.category,
                description=f"[Team Work] {approval.description}",
                amount=approval.amount,
                expense_date=approval.expense_date
            )
            
            Notification.objects.create(
                user=approval.submitted_by,
                message=f"✅ Your team expense submission of {approval.amount} under {approval.category} was APPROVED by {request.user.username}."
            )
            
            UserActivityLog.objects.create(
                user=request.user,
                action=f"Approved team expense submission #{approval_id}"
            )
            return JsonResponse({'success': True, 'msg': 'Expense approved and logged.'})
            
        elif action == 'reject':
            approval.status = 'rejected'
            approval.approved_by = request.user
            approval.save()
            
            Notification.objects.create(
                user=approval.submitted_by,
                message=f"❌ Your team expense submission of {approval.amount} under {approval.category} was REJECTED by {request.user.username}."
            )
            
            UserActivityLog.objects.create(
                user=request.user,
                action=f"Rejected team expense submission #{approval_id}"
            )
            return JsonResponse({'success': True, 'msg': 'Expense rejected.'})
            
        return JsonResponse({'success': False, 'error': 'Invalid action choice.'})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# Helper: Seed Marketplace Products and Vendors dynamically
def seed_marketplace_products():
    from django.contrib.auth.models import User
    from expenses.models import Vendor, MarketplaceProduct
    
    vendors_info = [
        {'username': 'taxsoft', 'email': 'taxsoft@example.com', 'company': 'TaxSoft Inc.', 'desc': 'Tax optimizer developer', 'phone': '+917845782348'},
        {'username': 'slacktech', 'email': 'slacktech@example.com', 'company': 'Slack Technologies', 'desc': 'Slack integration publisher', 'phone': '+917845782348'},
        {'username': 'intuit', 'email': 'intuit@example.com', 'company': 'Intuit Inc.', 'desc': 'QuickBooks developer', 'phone': '+917845782348'},
        {'username': 'hdfc_adv', 'email': 'hdfc_adv@example.com', 'company': 'HDFC Bank', 'desc': 'Investment and Mutual Fund Advisory', 'phone': '+917845782348'},
        {'username': 'allianz', 'email': 'allianz@example.com', 'company': 'Allianz Group', 'desc': 'SafeGuard insurance protection providers', 'phone': '+917845782348'},
    ]
    
    for v in vendors_info:
        user, _ = User.objects.get_or_create(username=v['username'], defaults={'email': v['email']})
        profile = user.profile
        profile.whatsapp_number = v['phone']
        profile.save()
        
        Vendor.objects.get_or_create(
            user=user,
            defaults={
                'company_name': v['company'],
                'description': v['desc'],
                'is_approved': True
            }
        )
        
    products_info = [
        {
            'vendor_username': 'taxsoft',
            'name': 'SmartSpend Tax Optimizer',
            'desc': 'Automatically categorize and compile your tax returns. Instantly exports write-offs directly to standard regional IRS/Income Tax formats.',
            'price': 499.00,
            'category': 'Software'
        },
        {
            'vendor_username': 'slacktech',
            'name': 'Slack Expense Integration',
            'desc': 'Add expenses directly from your company Slack channels using simple commands like /spend 45.00 on Coffee.',
            'price': 299.00,
            'category': 'Software'
        },
        {
            'vendor_username': 'intuit',
            'name': 'QuickBooks Ledger Connect',
            'desc': 'Synchronize monthly corporate expenditures and team budgets directly into corporate ledger charts in QuickBooks.',
            'price': 799.00,
            'category': 'Software'
        },
        {
            'vendor_username': 'hdfc_adv',
            'name': 'HDFC Mutual Fund Advisor',
            'desc': 'Invest your trackable monthly savings balance into top-performing mutual funds directly based on custom AI advice.',
            'price': 199.00,
            'category': 'Services'
        },
        {
            'vendor_username': 'allianz',
            'name': 'Allianz SafeGuard Insurance',
            'desc': 'Get curated quotes for life, health, auto, and travel insurance coverage, automatically billed straight to your Bills category.',
            'price': 999.00,
            'category': 'Services'
        }
    ]
    
    for p in products_info:
        vendor_user = User.objects.get(username=p['vendor_username'])
        vendor = vendor_user.vendor_profile
        
        MarketplaceProduct.objects.get_or_create(
            vendor=vendor,
            name=p['name'],
            defaults={
                'description': p['desc'],
                'price': p['price'],
                'category': p['category']
            }
        )


# ─── SmartSpend Marketplace View ──────────────────────────────────────────────
@login_required
def marketplace_view(request):
    if MarketplaceProduct.objects.count() == 0:
        try:
            seed_marketplace_products()
        except Exception as e:
            print("Seeding error:", str(e))
            
    products = MarketplaceProduct.objects.filter(vendor__is_approved=True).order_by('product_id')
    prefs = get_user_preferences(request)
    return render(request, 'expenses/marketplace.html', {'prefs': prefs, 'products': products})


@csrf_exempt
@login_required
def create_marketplace_order_ajax(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        if not product_id:
            return JsonResponse({'success': False, 'error': 'Missing product_id.'})
            
        product = MarketplaceProduct.objects.filter(product_id=product_id).first()
        if not product:
            return JsonResponse({'success': False, 'error': 'Product not found.'})
            
        buyer = request.user
        vendor = product.vendor
        seller = vendor.user
        
        # 1. Create MarketplaceOrder
        order = MarketplaceOrder.objects.create(
            product=product,
            buyer=buyer,
            vendor=vendor,
            price_at_purchase=product.price,
            status='completed'
        )
        
        # 2. Log Expense for buyer
        expense = Expense.objects.create(
            user=buyer,
            category='Shopping',
            description=f"Marketplace Purchase: {product.name}",
            amount=product.price,
            expense_date=date.today()
        )
        
        # 3. Create Dashboard Notifications
        buyer_msg = f"🎉 Success! You have purchased '{product.name}' for ₹{product.price:.2f}. The expense has been logged."
        seller_msg = f"💰 Sale Alert! Your product '{product.name}' was purchased by {buyer.username} for ₹{product.price:.2f}."
        
        Notification.objects.create(user=buyer, message=buyer_msg)
        Notification.objects.create(user=seller, message=seller_msg)
        
        # 4. Log AdminNotification
        AdminNotification.objects.create(
            event_type='marketplace_order',
            message=f"User {buyer.username} purchased '{product.name}' (ID: {product.product_id}) for ₹{product.price:.2f} from vendor {vendor.company_name}."
        )
        
        # 5. Send WhatsApp notifications
        whatsapp_buyer_msg = (
            f"🔔 *SmartSpend Purchase Confirmation*\n\n"
            f"Hello *{buyer.username}*,\n"
            f"Your purchase of *{product.name}* for *₹{product.price:.2f}* was successful!\n\n"
            f"📂 Category: Shopping\n"
            f"📝 Description: {product.description[:100]}...\n\n"
            f"Thank you for using SmartSpend!"
        )
        
        whatsapp_seller_msg = (
            f"🔔 *SmartSpend Sale Notification*\n\n"
            f"Hello *{seller.username}*,\n"
            f"Your integration product *{product.name}* has been purchased!\n\n"
            f"👤 Buyer: {buyer.username}\n"
            f"💰 Amount: ₹{product.price:.2f}\n"
            f"📅 Date: {date.today().strftime('%Y-%m-%d')}"
        )
        
        whatsapp_admin_msg = (
            f"🔔 *SmartSpend Admin System Notice*\n\n"
            f"New Marketplace transaction completed!\n"
            f"👤 Buyer: {buyer.username}\n"
            f"💼 Seller/Vendor: {vendor.company_name} ({seller.username})\n"
            f"📦 Product: {product.name}\n"
            f"💰 Amount: ₹{product.price:.2f}"
        )
        
        # Send to buyer
        buyer_phone = buyer.profile.whatsapp_number
        if buyer_phone:
            try:
                send_whatsapp_message(buyer_phone, whatsapp_buyer_msg)
            except Exception as e:
                print(f"Failed to send buyer whatsapp to {buyer_phone}: {e}")
                
        # Send to seller
        seller_phone = seller.profile.whatsapp_number
        if seller_phone:
            try:
                send_whatsapp_message(seller_phone, whatsapp_seller_msg)
            except Exception as e:
                print(f"Failed to send seller whatsapp to {seller_phone}: {e}")
                
        # Send to admin/owner
        admin_phone = getattr(settings, 'ADMIN_WHATSAPP_NUMBER', '+919944550063')
        if admin_phone:
            try:
                send_whatsapp_message(admin_phone, whatsapp_admin_msg)
            except Exception as e:
                print(f"Failed to send admin whatsapp to {admin_phone}: {e}")
                
        return JsonResponse({
            'success': True,
            'msg': 'Order processed and expense logged successfully.',
            'order_id': order.order_id,
            'expense_id': expense.expense_id
        })
        
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# ─── Mobile Experience & Widget Simulator ────────────────────────────────────
@login_required
def mobile_preview_view(request):
    prefs = get_user_preferences(request)
    profile = request.user.profile
    
    today = date.today()
    daily_spent = Expense.objects.filter(user=request.user, expense_date=today).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
    
    budgets = Budget.objects.filter(user=request.user)
    budget_data = []
    start_of_month = date(today.year, today.month, 1)
    for b in budgets[:3]:
        spent = Expense.objects.filter(user=request.user, category=b.category, expense_date__gte=start_of_month).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        pct = (spent / b.limit_amount) * 100 if b.limit_amount > 0 else 0
        budget_data.append({
            'category': b.category,
            'spent': spent,
            'limit': b.limit_amount,
            'percentage': min(pct, 100)
        })
        
    context = {
        'prefs': prefs,
        'profile': profile,
        'daily_spent': daily_spent,
        'budget_data': budget_data
    }
    return render(request, 'expenses/mobile_preview.html', context)


# ─── Support Community Forum Views ───────────────────────────────────────────
@login_required
def forum_view(request):
    from django.db.models import Count
    from expenses.models import ForumPost
    prefs = get_user_preferences(request)
    posts = ForumPost.objects.select_related('user').annotate(
        comment_count=Count('comments'), 
        upvote_count=Count('upvotes')
    ).order_by('-created_at')
    
    return render(request, 'expenses/forum.html', {'prefs': prefs, 'posts': posts})


@login_required
def forum_detail_view(request, post_id):
    from django.db.models import Count
    from expenses.models import ForumPost
    prefs = get_user_preferences(request)
    post = get_object_or_404(
        ForumPost.objects.select_related('user').annotate(upvote_count=Count('upvotes')), 
        pk=post_id
    )
    comments = post.comments.select_related('user').order_by('created_at')
    
    return render(request, 'expenses/forum_detail.html', {
        'prefs': prefs,
        'post': post,
        'comments': comments
    })


@csrf_exempt
@login_required
def create_forum_post_ajax(request):
    if request.method == 'POST':
        from expenses.models import ForumPost
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        if title and content:
            post = ForumPost.objects.create(
                user=request.user,
                title=title,
                content=content
            )
            UserActivityLog.objects.create(
                user=request.user,
                action=f"Created forum post #{post.post_id}: {title}"
            )
            return JsonResponse({'success': True, 'post_id': post.post_id})
        return JsonResponse({'success': False, 'error': 'Title and Content are required.'})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


@csrf_exempt
@login_required
def upvote_forum_post_ajax(request):
    if request.method == 'POST':
        from expenses.models import ForumPost
        post_id = request.POST.get('post_id')
        post = get_object_or_404(ForumPost, pk=post_id)
        if post.upvotes.filter(id=request.user.id).exists():
            post.upvotes.remove(request.user)
            upvoted = False
        else:
            post.upvotes.add(request.user)
            upvoted = True
            
        return JsonResponse({'success': True, 'upvoted': upvoted, 'count': post.upvotes.count()})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


@csrf_exempt
@login_required
def create_forum_comment_ajax(request):
    if request.method == 'POST':
        from expenses.models import ForumPost, ForumComment
        post_id = request.POST.get('post_id')
        content = request.POST.get('content', '').strip()
        post = get_object_or_404(ForumPost, pk=post_id)
        if content:
            comment = ForumComment.objects.create(
                post=post,
                user=request.user,
                content=content
            )
            UserActivityLog.objects.create(
                user=request.user,
                action=f"Commented on forum post #{post_id}"
            )
            return JsonResponse({
                'success': True, 
                'username': request.user.username,
                'content': comment.content,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M')
            })
        return JsonResponse({'success': False, 'error': 'Comment content cannot be empty.'})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


@csrf_exempt
@login_required
def report_forum_post_ajax(request):
    if request.method == 'POST':
        from expenses.models import ForumPost, ForumPostReport
        post_id = request.POST.get('post_id')
        reason = request.POST.get('reason', '').strip()
        if not post_id or not reason:
            return JsonResponse({'success': False, 'error': 'Post ID and reason are required.'})
        post = get_object_or_404(ForumPost, pk=post_id)
        report = ForumPostReport.objects.create(post=post, user=request.user, reason=reason)
        # Log AdminNotification for Forum Reports
        AdminNotification.objects.create(
            event_type='forum_report',
            message=f"Forum post #{post.post_id} reported by {request.user.username}. Reason: {reason}"
        )
        return JsonResponse({'success': True, 'msg': 'Post reported successfully.'})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


# ─── Enterprise Reporting: Excel Spreadsheet Export ─────────────────────────
@login_required
def export_excel(request):
    user = request.user
    expenses = Expense.objects.filter(user=user).order_by('-expense_date')
    budgets = Budget.objects.filter(user=user)
    
    xml_content = """<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:x="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <Styles>
  <Style ss:ID="Default" ss:Name="Normal">
   <Alignment ss:Vertical="Bottom"/>
   <Borders/>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"/>
   <Interior/>
   <NumberFormat/>
   <Protection/>
  </Style>
  <Style ss:ID="Header">
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="12" ss:Color="#FFFFFF" ss:Bold="1"/>
   <Interior ss:Color="#6366F1" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="Title">
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="16" ss:Bold="1"/>
  </Style>
 </Styles>
 <Worksheet ss:Name="Expenses">
  <Table>
   <Column ss:Width="100"/>
   <Column ss:Width="120"/>
   <Column ss:Width="200"/>
   <Column ss:Width="100"/>
   <Row>
    <Cell ss:StyleID="Title"><Data ss:Type="String">SmartSpend - Transaction History</Data></Cell>
   </Row>
   <Row><Cell><Data ss:Type="String">User: """ + user.username + """</Data></Cell></Row>
   <Row/>
   <Row ss:StyleID="Header">
    <Cell><Data ss:Type="String">Date</Data></Cell>
    <Cell><Data ss:Type="String">Category</Data></Cell>
    <Cell><Data ss:Type="String">Description</Data></Cell>
    <Cell><Data ss:Type="String">Amount</Data></Cell>
   </Row>
"""
    for exp in expenses:
        xml_content += f"""   <Row>
    <Cell><Data ss:Type="String">{exp.expense_date.strftime('%Y-%m-%d')}</Data></Cell>
    <Cell><Data ss:Type="String">{exp.category}</Data></Cell>
    <Cell><Data ss:Type="String">{exp.description}</Data></Cell>
    <Cell><Data ss:Type="Number">{float(exp.amount)}</Data></Cell>
   </Row>
"""
        
    xml_content += """  </Table>
 </Worksheet>
 <Worksheet ss:Name="Budgets">
  <Table>
   <Column ss:Width="150"/>
   <Column ss:Width="100"/>
   <Row>
    <Cell ss:StyleID="Title"><Data ss:Type="String">Monthly Budget Limits</Data></Cell>
   </Row>
   <Row/>
   <Row ss:StyleID="Header">
    <Cell><Data ss:Type="String">Category</Data></Cell>
    <Cell><Data ss:Type="String">Limit Amount</Data></Cell>
   </Row>
"""
    for b in budgets:
        xml_content += f"""   <Row>
    <Cell><Data ss:Type="String">{b.category}</Data></Cell>
    <Cell><Data ss:Type="Number">{float(b.limit_amount)}</Data></Cell>
   </Row>
"""
        
    xml_content += """  </Table>
 </Worksheet>
</Workbook>
"""
    
    response = HttpResponse(xml_content, content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = f'attachment; filename="smartspend_report_{user.username}.xml"'
    
    UserActivityLog.objects.create(
        user=user,
        action="Exported spreadsheet data to Excel compatible XML format"
    )
    return response


# ─── Settings Security Center View ───────────────────────────────────────────
@login_required
def security_settings(request):
    from expenses.models import UserDeviceSession
    prefs = get_user_preferences(request)
    profile = request.user.profile
    
    if request.method == 'POST':
        mfa_enabled = request.POST.get('mfa_enabled') == 'on'
        profile.mfa_enabled = mfa_enabled
        profile.save()
        UserActivityLog.objects.create(
            user=request.user,
            action=f"Updated MFA settings to: {mfa_enabled}"
        )
        return redirect('security_settings')
        
    device_sessions = UserDeviceSession.objects.filter(user=request.user).order_by('-last_activity')
    
    context = {
        'prefs': prefs,
        'profile': profile,
        'device_sessions': device_sessions,
    }
    return render(request, 'expenses/security.html', context)

@login_required
def revoke_device_session(request, session_id):
    from expenses.models import UserDeviceSession
    session = get_object_or_404(UserDeviceSession, id=session_id, user=request.user)
    UserActivityLog.objects.create(
        user=request.user,
        action=f"Revoked device session: {session.ip_address} | {session.user_agent[:40]}..."
    )
    session.delete()
    return redirect('security_settings')

# ─── Marketing Blog Views ───────────────────────────────────────────────────
def blog_list(request):
    from expenses.models import BlogPost
    prefs = get_user_preferences(request)
    posts = BlogPost.objects.filter(is_published=True).order_by('-created_at')
    return render(request, 'expenses/blog.html', {'prefs': prefs, 'posts': posts})

def blog_detail(request, slug):
    from expenses.models import BlogPost
    prefs = get_user_preferences(request)
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)
    return render(request, 'expenses/blog_detail.html', {'prefs': prefs, 'post': post})

# ─── SEO robots.txt & sitemap.xml Views ──────────────────────────────────────
def sitemap_view(request):
    from expenses.models import BlogPost
    from django.urls import reverse
    
    pages = [
        reverse('landing'),
        reverse('about'),
        reverse('features'),
        reverse('pricing'),
        reverse('contact'),
    ]
    
    posts = BlogPost.objects.filter(is_published=True)
    domain = request.build_absolute_uri('/')[:-1]
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for page in pages:
        xml += f'  <url>\n    <loc>{domain}{page}</loc>\n    <changefreq>daily</changefreq>\n  </url>\n'
        
    for post in posts:
        xml += f'  <url>\n    <loc>{domain}{reverse("blog_detail", args=[post.slug])}</loc>\n    <changefreq>weekly</changefreq>\n  </url>\n'
        
    xml += '</urlset>\n'
    return HttpResponse(xml, content_type='application/xml')

def robots_view(request):
    content = "User-agent: *\nDisallow: /admin/\nDisallow: /admin-dashboard/\nDisallow: /dashboard/\nDisallow: /api/\nSitemap: " + request.build_absolute_uri('/sitemap.xml') + "\n"
    return HttpResponse(content, content_type='text/plain')

# ─── Developer Keys Management Views ──────────────────────────────────────────
@login_required
def developer_keys_view(request):
    from expenses.models import DeveloperApiKey
    prefs = get_user_preferences(request)
    keys = DeveloperApiKey.objects.filter(user=request.user, is_active=True).order_by('-created_at')
    
    new_key = request.session.pop('new_generated_key', None)
    
    context = {
        'prefs': prefs,
        'keys': keys,
        'new_key': new_key,
    }
    return render(request, 'expenses/developer_keys.html', context)

@csrf_exempt
@login_required
def create_developer_key_ajax(request):
    if request.method == 'POST':
        from expenses.models import DeveloperApiKey
        import secrets
        import hashlib
        
        name = request.POST.get('name', 'My API Key').strip()
        prefix = secrets.token_hex(4)
        secret = secrets.token_urlsafe(32)
        full_key = f"sk_{prefix}_{secret}"
        
        secret_hash = hashlib.sha256(full_key.encode('utf-8')).hexdigest()
        
        DeveloperApiKey.objects.create(
            user=request.user,
            name=name,
            key_prefix=prefix,
            secret_key_hash=secret_hash,
            rate_limit=60
        )
        
        request.session['new_generated_key'] = full_key
        
        UserActivityLog.objects.create(
            user=request.user,
            action=f"Created Developer API Key: {name} ({prefix}...)"
        )
        
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})

@csrf_exempt
@login_required
def revoke_developer_key_ajax(request):
    if request.method == 'POST':
        from expenses.models import DeveloperApiKey
        key_id = request.POST.get('key_id')
        key_obj = get_object_or_404(DeveloperApiKey, id=key_id, user=request.user)
        key_obj.is_active = False
        key_obj.save()
        
        UserActivityLog.objects.create(
            user=request.user,
            action=f"Revoked Developer API Key: {key_obj.name} ({key_obj.key_prefix}...)"
        )
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


def prometheus_metrics(request):
    # Calculate metrics dynamically
    total_users = User.objects.count()
    total_expenses = Expense.objects.count()
    
    cpu_percent = 0.0
    memory_bytes = 0
    try:
        import psutil
        process = psutil.Process()
        cpu_percent = process.cpu_percent(interval=0.1)
        memory_bytes = process.memory_info().rss
    except Exception:
        pass
        
    metrics = [
        f"# HELP smartspend_users_total Total number of registered users",
        f"# TYPE smartspend_users_total counter",
        f"smartspend_users_total {total_users}",
        f"# HELP smartspend_expenses_total Total number of expenses logged",
        f"# TYPE smartspend_expenses_total counter",
        f"smartspend_expenses_total {total_expenses}",
        f"# HELP smartspend_process_cpu_usage_percent CPU usage percentage of the process",
        f"# TYPE smartspend_process_cpu_usage_percent gauge",
        f"smartspend_process_cpu_usage_percent {cpu_percent}",
        f"# HELP smartspend_process_memory_bytes Memory usage in bytes of the process",
        f"# TYPE smartspend_process_memory_bytes gauge",
        f"smartspend_process_memory_bytes {memory_bytes}",
    ]
    return HttpResponse("\n".join(metrics) + "\n", content_type="text/plain; version=0.0.4")


