from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from expenses.models import Expense, Budget, Notification, Profile, SavingsChallenge
from datetime import date, timedelta
from django.db.models import Sum, Avg
from decimal import Decimal

class Command(BaseCommand):
    help = "Runs daily reminders, weekly summaries, and monthly budget breach checks."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting automation tasks..."))
        today = date.today()
        start_of_month = date(today.year, today.month, 1)
        
        users = User.objects.filter(is_active=True)
        self.stdout.write(f"Processing automations for {users.count()} active users.")
        
        for u in users:
            profile, _ = Profile.objects.get_or_create(user=u)
            currency_symbol = '₹' if profile.currency == 'INR' else '$' if profile.currency == 'USD' else '€' if profile.currency == 'EUR' else '£' if profile.currency == 'GBP' else '¥'
            
            # 1. Daily Expense Logging Reminder
            has_logged_today = Expense.objects.filter(user=u, expense_date=today).exists()
            if not has_logged_today:
                Notification.objects.create(
                    user=u,
                    message="📢 Daily Reminder: You have not logged any expenses today. Don't forget to track your spending!"
                )
                self.stdout.write(f"Created daily reminder for {u.username}")

            # 2. Weekly Spending Summary (for past 7 days)
            seven_days_ago = today - timedelta(days=7)
            weekly_expenses = Expense.objects.filter(user=u, expense_date__gte=seven_days_ago, expense_date__lte=today)
            weekly_total = weekly_expenses.aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
            weekly_count = weekly_expenses.count()
            
            if weekly_count > 0:
                Notification.objects.create(
                    user=u,
                    message=f"📊 Weekly Summary: You spent a total of {currency_symbol}{weekly_total:.2f} across {weekly_count} transactions in the past 7 days."
                )
                self.stdout.write(f"Created weekly summary for {u.username}")

            # 3. Monthly Budget Alerts
            budgets = Budget.objects.filter(user=u)
            for b in budgets:
                category_spent = Expense.objects.filter(
                    user=u, 
                    category=b.category,
                    expense_date__gte=start_of_month,
                    expense_date__lte=today
                ).aggregate(t=Sum('amount'))['t'] or Decimal(0.0)
                
                # If spent > 90% of limit
                if category_spent >= b.limit_amount * Decimal(0.9):
                    breach_pct = (category_spent / b.limit_amount) * 100
                    status_msg = "exceeded" if category_spent >= b.limit_amount else "approaching"
                    
                    Notification.objects.create(
                        user=u,
                        message=f"⚠️ Budget Alert: You have spent {currency_symbol}{category_spent:.2f} in {b.category}, which is {breach_pct:.1f}% of your limit ({currency_symbol}{b.limit_amount:.2f})! You are {status_msg} your budget."
                    )
                    self.stdout.write(f"Created budget alert for {u.username} (Category: {b.category})")
            
            # 4. Spending Spike Detection (exceeding 3x historical average amount)
            today_expenses = Expense.objects.filter(user=u, expense_date=today)
            for exp in today_expenses:
                historical_avg_dict = Expense.objects.filter(user=u).exclude(expense_id=exp.expense_id).aggregate(avg=Avg('amount'))
                historical_avg = historical_avg_dict['avg']
                if historical_avg is not None:
                    historical_avg_decimal = Decimal(str(historical_avg))
                    if exp.amount > Decimal('3') * historical_avg_decimal:
                        Notification.objects.create(
                            user=u,
                            message=f"⚠️ Spending Spike Alert: Your expense of {currency_symbol}{exp.amount:.2f} in category '{exp.category}' is more than 3x your historical average transaction size of {currency_symbol}{historical_avg_decimal:.2f}!"
                        )
                        self.stdout.write(f"Created spending spike alert for {u.username} on expense {exp.expense_id}")

            # 5. Savings Milestone Completion
            uncompleted_challenges = SavingsChallenge.objects.filter(user=u, is_completed=False)
            for challenge in uncompleted_challenges:
                if challenge.current_amount >= challenge.target_amount:
                    challenge.is_completed = True
                    challenge.save()
                    Notification.objects.create(
                        user=u,
                        message=f"🎯 Savings Milestone Reached! Congratulations, you have completed your savings challenge '{challenge.title}' by reaching your target of {currency_symbol}{challenge.target_amount:.2f}!"
                    )
                    self.stdout.write(f"Completed savings challenge '{challenge.title}' for {u.username}")
                    
        self.stdout.write(self.style.SUCCESS("All automation tasks executed successfully!"))
