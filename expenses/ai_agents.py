from decimal import Decimal
from datetime import date, timedelta
from django.db.models import Sum, Avg, Count
from expenses.models import Expense, Budget, SavingsChallenge, SupportTicket

class ExpenseAgent:
    """
    Analyzes transactions, detects duplicates, and auto-suggests categories.
    """
    @staticmethod
    def detect_duplicates(user):
        """
        Detects expenses logged on the same day with same amount and category.
        """
        duplicates = []
        today = date.today()
        # Look back 30 days
        thirty_days_ago = today - timedelta(days=30)
        
        expenses = Expense.objects.filter(user=user, expense_date__gte=thirty_days_ago).order_by('expense_date', 'expense_id')
        seen = {}
        for exp in expenses:
            key = (exp.expense_date, float(exp.amount), exp.category)
            if key in seen:
                duplicates.append({
                    'original': seen[key],
                    'duplicate': exp
                })
            else:
                seen[key] = exp
        return duplicates

    @staticmethod
    def auto_categorize(description):
        """
        Suggests categories based on keywords.
        """
        desc = description.lower()
        if any(w in desc for w in ['pizza', 'food', 'restaurant', 'lunch', 'dinner', 'cafe', 'swiggy', 'zomato', 'eat']):
            return 'Food'
        if any(w in desc for w in ['uber', 'ola', 'taxi', 'bus', 'train', 'flight', 'metro', 'travel', 'fuel', 'petrol', 'diesel']):
            return 'Travel'
        if any(w in desc for w in ['rent', 'room', 'flat', 'apartment', 'pg']):
            return 'Rent'
        if any(w in desc for w in ['electricity', 'water', 'internet', 'wifi', 'recharge', 'bills', 'gas', 'postpaid']):
            return 'Bills'
        if any(w in desc for w in ['amazon', 'flipkart', 'myntra', 'clothes', 'shoes', 'mall', 'shopping']):
            return 'Shopping'
        if any(w in desc for w in ['netflix', 'movie', 'show', 'game', 'fun', 'entertainment', 'spotify', 'prime']):
            return 'Entertainment'
        if any(w in desc for w in ['doctor', 'medicine', 'hospital', 'health', 'gym', 'pharmacy', 'clinic']):
            return 'Health'
        return 'Other'


class BudgetAgent:
    """
    Forecasts overspending and warns users.
    """
    @staticmethod
    def forecast_budget_status(user):
        """
        Analyzes current budgets and predicts if user will exceed them.
        """
        warnings = []
        today = date.today()
        start_of_month = date(today.year, today.month, 1)
        days_in_month = 30 # average
        days_passed = (today - start_of_month).days or 1
        
        budgets = Budget.objects.filter(user=user)
        for b in budgets:
            spent = Expense.objects.filter(
                user=user, 
                category=b.category,
                expense_date__gte=start_of_month,
                expense_date__lte=today
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
            
            daily_rate = float(spent) / days_passed
            projected = daily_rate * days_in_month
            limit = float(b.limit_amount)
            
            if projected > limit:
                warnings.append({
                    'category': b.category,
                    'spent': float(spent),
                    'limit': limit,
                    'projected': projected,
                    'risk_level': 'High' if float(spent) > limit else 'Medium'
                })
        return warnings


class SavingsAgent:
    """
    Helps plan savings goals and projects milestones.
    """
    @staticmethod
    def get_savings_tips(user):
        """
        Recommends plans to achieve active savings goals.
        """
        tips = []
        challenges = SavingsChallenge.objects.filter(user=user, is_completed=False)
        for c in challenges:
            days_left = (c.end_date - date.today()).days
            needed = float(c.target_amount - c.current_amount)
            if needed > 0:
                if days_left > 0:
                    daily_need = needed / days_left
                    tips.append(
                        f"🎯 **Goal '{c.title}':** To save {c.target_amount:.2f} by {c.end_date}, you need to save **{daily_need:.2f}** per day for the next {days_left} days."
                    )
                else:
                    tips.append(
                        f"⚠️ **Goal '{c.title}':** Your target date has passed! You need **{needed:.2f}** to complete your goal."
                    )
        if not tips:
            tips.append("💡 Set a new Savings Challenge in the Achievements section to receive tailored compound savings tips!")
        return tips


class AnalyticsAgent:
    """
    Tracks transaction anomalies and flags spending spikes.
    """
    @staticmethod
    def detect_spending_spikes(user):
        """
        Flags single transactions that are > 3x the user's historical average.
        """
        spikes = []
        avg_expense = Expense.objects.filter(user=user).aggregate(a=Avg('amount'))['a']
        if avg_expense:
            threshold = avg_expense * Decimal('3.0')
            large_expenses = Expense.objects.filter(user=user, amount__gte=threshold).order_by('-expense_date')[:5]
            for exp in large_expenses:
                spikes.append({
                    'expense_id': exp.expense_id,
                    'category': exp.category,
                    'amount': float(exp.amount),
                    'average': float(avg_expense),
                    'description': exp.description,
                    'date': exp.expense_date
                })
        return spikes


class SupportAgent:
    """
    Intelligently answers support questions using the Knowledge Base.
    """
    @staticmethod
    def match_faq(query):
        """
        Matches a natural query to predefined FAQs.
        """
        q = query.lower()
        faqs = [
            {
                'q': "how do i change currency settings?",
                'keywords': ['currency', 'convert', 'inr', 'usd', 'eur', 'change currency'],
                'a': "Navigate to the Settings page, choose your primary currency from the dropdown (supporting INR, USD, EUR, GBP, AED, SGD, JPY, AUD, CAD), and click Save Preferences."
            },
            {
                'q': "how do i enable multi-factor authentication (mfa)?",
                'keywords': ['mfa', 'otp', 'two factor', 'security', 'verify', 'login'],
                'a': "Go to the Settings page, check the box labeled 'Enable Multi-Factor Authentication (MFA via OTP)', and click Save. On your next login, you will be prompted to enter a 6-digit verification code."
            },
            {
                'q': "how do i download or delete my personal data?",
                'keywords': ['gdpr', 'export', 'delete data', 'purge', 'delete account'],
                'a': "Under the GDPR Privacy Controls section on the Settings page, you can click 'Export Data (JSON)' to download a backup of your personal information, or click 'Purge Account' to permanently scrub all your records from our systems."
            },
            {
                'q': "how does the voice assistant work?",
                'keywords': ['voice', 'speech', 'record', 'mic', 'say'],
                'a': "Click the microphone button on the User Dashboard and speak naturally, e.g. 'spent 250 on food for pizza'. The AI engine will parse the transaction details and add it automatically."
            }
        ]
        
        for faq in faqs:
            if any(keyword in q for keyword in faq['keywords']):
                return f"🤖 **Support Agent suggestion:** {faq['a']}"
                
        return "I couldn't find a direct FAQ answer. Please open a support ticket in the Support Desk or contact our support team!"
