from datetime import date, timedelta
from django.db.models import Sum
from .models import Expense, Budget
import random

def get_chatbot_response(user, query):
    """
    Evaluates user queries and returns text responses based on database data.
    """
    if not query:
        return "Please ask me something! I'm your SmartSpend AI assistant."
    
    query = query.lower().strip()
    today = date.today()
    start_of_month = date(today.year, today.month, 1)

    # Admin commands through chatbot (only if user is staff/superuser)
    if user.is_staff or user.is_superuser:
        # Check command structure: "admin grant <username>", "admin revoke <username>", "admin list users"
        if query.startswith("admin grant "):
            target_username = query.replace("admin grant ", "").strip()
            from django.contrib.auth.models import User
            target = User.objects.filter(username__iexact=target_username).first()
            if target:
                target.is_staff = True
                target.save()
                return f"🛡️ **Admin Rights Granted:** User '{target.username}' is now a staff member."
            return f"❌ User '{target_username}' not found."
            
        elif query.startswith("admin revoke "):
            target_username = query.replace("admin revoke ", "").strip()
            from django.contrib.auth.models import User
            target = User.objects.filter(username__iexact=target_username).first()
            if target:
                if target.is_superuser:
                    return f"❌ Cannot revoke rights from superuser '{target.username}'."
                target.is_staff = False
                target.save()
                return f"📉 **Admin Rights Revoked:** User '{target.username}' is no longer a staff member."
            return f"❌ User '{target_username}' not found."
            
        elif query == "admin list users":
            from django.contrib.auth.models import User
            all_users = User.objects.all().order_by('-date_joined')
            lines = ["👥 **Registered SmartSpend Users:**"]
            for u in all_users:
                role = "Superuser 🛡️" if u.is_superuser else "Staff 💼" if u.is_staff else "Standard User 👤"
                lines.append(f"- **{u.username}** ({u.email or 'No email'}) - *{role}*")
            return "\n".join(lines)
    
    # Check for hotspot query: "where did I spend most this month?"
    if any(w in query for w in ["spend most", "highest spending", "most spent", "biggest expense", "hotspot"]):
        top_category = Expense.objects.filter(user=user, expense_date__gte=start_of_month)\
                              .values('category')\
                              .annotate(total=Sum('amount'))\
                              .order_by('-total')\
                              .first()
        if top_category:
            return f"🔥 **Spending Hotspot:** You spent the most on **{top_category['category']}** this month, totaling **{top_category['total']:.2f}**."
        return "You have not logged any expenses this month yet."

    # Check for specific category spending queries
    categories = ['food', 'travel', 'rent', 'bills', 'shopping', 'entertainment', 'health', 'other']
    matched_category = None
    for category in categories:
        if category in query:
            matched_category = category.capitalize()
            break
            
    if matched_category and any(w in query for w in ["how much", "spend", "expense", "total", "cost"]):
        total = Expense.objects.filter(
            user=user, 
            category=matched_category,
            expense_date__gte=start_of_month
        ).aggregate(total=Sum('amount'))['total'] or 0.0
        
        # Get budget limit if exists
        budget = Budget.objects.filter(user=user, category=matched_category).first()
        budget_str = ""
        if budget:
            budget_str = f" Your budget limit for {matched_category} is {budget.limit_amount:.2f}."
            if total > budget.limit_amount:
                budget_str += f" ⚠️ You have exceeded this budget by {(total - budget.limit_amount):.2f}!"
            else:
                budget_str += f" You have {(budget.limit_amount - total):.2f} remaining."
        else:
            budget_str = " No budget set for this category."
                
        return f"You have spent **{total:.2f}** on **{matched_category}** this month.{budget_str}"

    # 2. Check for total expenses query
    if any(w in query for w in ["total", "spent in total", "how much did i spend", "all expenses"]):
        total = Expense.objects.filter(
            user=user,
            expense_date__gte=start_of_month
        ).aggregate(total=Sum('amount'))['total'] or 0.0
        return f"Your total expenses for this month ({today.strftime('%B %Y')}) are **{total:.2f}**."

    # 3. Check for budget status
    if any(w in query for w in ["overspend", "budget", "limit", "status"]):
        budgets = Budget.objects.filter(user=user)
        if not budgets.exists():
            return "You haven't set any monthly budgets yet! Go to the Budget Planner to set limits."
        
        exceeded = []
        under_budget = []
        for b in budgets:
            total = Expense.objects.filter(
                user=user,
                category=b.category,
                expense_date__gte=start_of_month
            ).aggregate(total=Sum('amount'))['total'] or 0.0
            
            if total > b.limit_amount:
                exceeded.append(f"**{b.category}** (Spent: {total:.2f} / Limit: {b.limit_amount:.2f} ❌)")
            elif total > b.limit_amount * 0.8:
                under_budget.append(f"**{b.category}** (Spent: {total:.2f} / Limit: {b.limit_amount:.2f} ⚠️ Near Limit)")
            else:
                under_budget.append(f"**{b.category}** (Spent: {total:.2f} / Limit: {b.limit_amount:.2f} ✅)")
                
        response = ""
        if exceeded:
            response += "⚠️ **Overspending Alert!** You have exceeded your budget for:\n" + "\n".join([f"- {item}" for item in exceeded]) + "\n\n"
        
        if under_budget:
            response += "📋 **Budget Status:**\n" + "\n".join([f"- {item}" for item in under_budget])
        
        return response if response else "All categories are within budget!"

    # 4. Expense prediction / forecasting
    if any(w in query for w in ["predict", "next month", "forecast", "prediction"]):
        all_expenses = Expense.objects.filter(user=user)
        if all_expenses.count() < 3:
            return "I need a bit more expense history (at least 3 records) to make a prediction for next month. Keep tracking!"
        
        # simple prediction: calculate average daily spend and multiply by 30
        first_expense = all_expenses.order_by('expense_date').first()
        days_diff = (date.today() - first_expense.expense_date).days or 1
        total_historical = all_expenses.aggregate(total=Sum('amount'))['total'] or 0.0
        daily_average = float(total_historical) / days_diff
        predicted_month = daily_average * 30
        
        return f"🔮 **AI Expense Forecast:** Based on your tracking history of {days_diff} days, your average daily expense is **{daily_average:.2f}**. " \
               f"I predict your total spending next month will be approximately **{predicted_month:.2f}**."

    # 5. Compound Savings Advisor / Savings Forecasting
    if any(w in query for w in ["compound savings", "savings forecast", "savings projection", "save in 5 years", "save in 10 years"]):
        all_expenses = Expense.objects.filter(user=user)
        total_historical = float(all_expenses.aggregate(total=Sum('amount'))['total'] or 0.0)
        
        # Assume a baseline income or default savings capacity: e.g. saving 20% of their historical monthly rate
        monthly_avg_spending = 1000.0
        if all_expenses.count() >= 3:
            first_expense = all_expenses.order_by('expense_date').first()
            days_diff = (date.today() - first_expense.expense_date).days or 1
            monthly_avg_spending = (total_historical / days_diff) * 30.0
            
        # Target: Save 20% of spending amount monthly
        monthly_savings = monthly_avg_spending * 0.20
        if monthly_savings < 10.0:
            monthly_savings = 100.0 # fallback default monthly savings
            
        # 1 year, 5 years, 10 years projections (compounded monthly at 7% interest rate)
        rate = 0.07
        n = 12 # monthly compounding
        
        def project(years):
            t = years
            # Future value of a series formula: FV = P * [((1 + r/n)**(nt) - 1) / (r/n)]
            fv = monthly_savings * (((1 + rate/n)**(n*t) - 1) / (rate/n))
            return fv
            
        fv_1 = project(1)
        fv_5 = project(5)
        fv_10 = project(10)
        
        return f"📈 **AI Savings Advisor (7% Annual Growth Projection):**\n" \
               f"If you save just 20% of your average monthly spend (**{monthly_savings:.2f}** per month):\n" \
               f"• In **1 Year**: You will accumulate **{fv_1:.2f}**\n" \
               f"• In **5 Years**: You will accumulate **{fv_5:.2f}**\n" \
               f"• In **10 Years**: You will accumulate **{fv_10:.2f}**\n\n" \
               f"💡 *Tip:* Pay yourself first! Automate transfers of this amount to a high-yield savings account on payday."

    # 6. Budgeting advice or savings tips
    if any(w in query for w in ["advice", "tip", "savings", "recommend", "how to save"]):
        # Custom personalized advice based on highest spend category
        top_category = Expense.objects.filter(user=user, expense_date__gte=start_of_month)\
                              .values('category')\
                              .annotate(total=Sum('amount'))\
                              .order_by('-total')\
                              .first()
                              
        personalized_tip = ""
        if top_category:
            cat = top_category['category']
            tot = top_category['total']
            potential = tot * 0.15
            personalized_tip = f"Reviewing your records, your highest spending category this month is **{cat}** ({tot:.2f}). " \
                               f"If you reduce your spend in {cat} by 15%, you could save **{potential:.2f}**! "
                               
        tips = [
            "Follow the 50/30/20 rule: 50% for needs, 30% for wants, and 20% for savings.",
            "Review your subscriptions! Cancel any membership or service you haven't used in the past 30 days.",
            "Plan your meals ahead of time. Food is typically the easiest category to cut down on by reducing dining out.",
            "Wait 48 hours before making any non-essential purchase. This prevents impulse buying.",
            "Set up automatic transfers to your savings account on payday to ensure you 'pay yourself first'.",
            "Try to track every tiny expense, including tea and snacks. Small leakages can sink a big ship!",
            "Review your energy bills. Unplugging electronics when not in use can save up to 10% on electric bills."
        ]
        return f"{personalized_tip}{random.choice(tips)}"

    # 6a. Month-over-Month comparison
    if any(w in query for w in ["compare this month", "last month", "mom comparison", "monthly comparison"]):
        this_month_total = Expense.objects.filter(user=user, expense_date__gte=start_of_month, expense_date__lte=today).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        
        first_day_last_month = (start_of_month - timedelta(days=1)).replace(day=1)
        last_day_last_month = start_of_month - timedelta(days=1)
        
        last_month_total = Expense.objects.filter(user=user, expense_date__gte=first_day_last_month, expense_date__lte=last_day_last_month).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        
        diff = this_month_total - last_month_total
        diff_pct = 0.0
        if last_month_total > 0:
            diff_pct = (float(diff) / float(last_month_total)) * 100
            
        direction = "increase" if diff > 0 else "decrease"
        status_symbol = "📈" if diff > 0 else "📉"
        
        return f"📊 **Month-over-Month Spending Comparison:**\n" \
               f"• **This Month ({today.strftime('%B')}):** {this_month_total:.2f}\n" \
               f"• **Last Month ({first_day_last_month.strftime('%B')}):** {last_month_total:.2f}\n" \
               f"• **Difference:** {status_symbol} {abs(diff):.2f} ({abs(diff_pct):.1f}% {direction}) compared to last month."

    # 6b. Top 10 expenses
    if any(w in query for w in ["top 10", "10 expenses", "biggest expenses", "largest expenses"]):
        top_expenses = Expense.objects.filter(user=user).order_by('-amount')[:10]
        if not top_expenses.exists():
            return "You don't have any logged expenses to analyze!"
            
        lines = ["🏆 **Your Top 10 Highest Expenses:**"]
        for i, exp in enumerate(top_expenses, 1):
            lines.append(f"{i}. **{exp.amount:.2f}** on *{exp.category}* - {exp.description} ({exp.expense_date})")
        return "\n".join(lines)

    # 6c. Where can I reduce spending?
    if any(w in query for w in ["reduce spending", "where can i save", "budget recommendations", "cut spending"]):
        from expenses.ai_agents import BudgetAgent, SavingsAgent
        warnings = BudgetAgent.forecast_budget_status(user)
        tips = SavingsAgent.get_savings_tips(user)
        
        response_lines = ["🔍 **AI Financial Copilot Spending Optimization:**"]
        if warnings:
            response_lines.append("⚠️ **High Risk Budgets:**")
            for w in warnings:
                response_lines.append(f"- Category **{w['category']}** is projected to spend **{w['projected']:.2f}** against a limit of **{w['limit']:.2f}** ({w['risk_level']} Risk). Reduce daily outflow here immediately!")
        else:
            response_lines.append("✅ All your current category budgets look safe for this month.")
            
        response_lines.append("\n🎯 **Personal Savings Insights:**")
        for tip in tips[:3]:
            response_lines.append(f"- {tip}")
            
        return "\n".join(response_lines)

    # 7. Support FAQ Matching Fallback
    from expenses.ai_agents import SupportAgent
    faq_response = SupportAgent.match_faq(query)
    if "Support Agent suggestion" in faq_response:
        return faq_response

    # 8. Fallback or generic help
    admin_options = ""
    if user.is_staff or user.is_superuser:
        admin_options = "\n\n🛡️ **Admin Chatbot Commands:**\n" \
                        "- *'admin list users'*\n" \
                        "- *'admin grant <username>'*\n" \
                        "- *'admin revoke <username>'*"
                        
    return "I can help you track and analyze your finances! You can ask me queries like:\n\n" \
           "- *'How much did I spend on food?'*\n" \
           "- *'Compare this month with last month'*\n" \
           "- *'Show my top 10 expenses'*\n" \
           "- *'Where can I reduce spending?'*\n" \
           "- *'Where did I spend most this month?'*\n" \
           "- *'What is my total monthly expense?'*\n" \
           "- *'Am I overspending?'*\n" \
           "- *'Predict next month expenses'*\n" \
           "- *'How much can I save in 5 years?'*\n" \
           "- *'Give me savings tips'*" + admin_options
