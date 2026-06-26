from django.test import TestCase
from django.contrib.auth.models import User
from .models import Expense, Budget, Profile, Team, SupportTicket, CURRENCY_CHOICES, TeamMembership, TeamExpenseApproval, ForumPost, ForumComment, SavingsChallenge
from .nlp import parse_expense_text
from .chatbot import get_chatbot_response
from decimal import Decimal
from datetime import timedelta

class ProfileSignalTest(TestCase):
    def test_profile_automatically_created_on_user_registration(self):
        user = User.objects.create_user(username='testuser', email='test@example.com', password='password123')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(user.profile.currency, 'INR')
        self.assertEqual(user.profile.theme, 'dark')

class NLPParserTest(TestCase):
    def test_extract_amount_and_category_food(self):
        amount, category, description = parse_expense_text("I spent 150.50 rupees on pizza")
        self.assertEqual(amount, 150.50)
        self.assertEqual(category, 'Food')
        self.assertEqual(description, 'pizza')

    def test_extract_amount_and_category_rent(self):
        amount, category, description = parse_expense_text("Paid 5000 for rent")
        self.assertEqual(amount, 5000.0)
        self.assertEqual(category, 'Rent')
        self.assertEqual(description, 'rent')

    def test_extract_amount_and_category_travel(self):
        amount, category, description = parse_expense_text("spent 200 on travel ticket")
        self.assertEqual(amount, 200.0)
        self.assertEqual(category, 'Travel')
        self.assertEqual(description, 'travel ticket')

    def test_no_amount_fallback(self):
        amount, category, description = parse_expense_text("lunch with friends")
        self.assertEqual(amount, 0.0)
        self.assertEqual(category, 'Food')
        self.assertEqual(description, 'lunch with friends')

class ChatbotEngineTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='chatuser', password='password123')

    def test_advice_tip_response(self):
        response = get_chatbot_response(self.user, "Give me budgeting advice")
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 10)

    def test_fallback_help_response(self):
        response = get_chatbot_response(self.user, "tell me a joke")
        self.assertIn("I can help you track and analyze your finances", response)

class ViewRoutingTest(TestCase):
    def test_landing_page_resolves(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_unauthenticated_dashboard_redirects(self):
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 302) # Redirects to login

class AJAXValidationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.login(username='testuser', password='password123')

    def test_edit_expense_invalid_id(self):
        response = self.client.post('/api/expense/edit/', {'expense_id': ''})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Invalid expense ID.')

    def test_delete_expense_invalid_id(self):
        response = self.client.post('/api/expense/delete/', {'expense_id': 'abc'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Invalid expense ID.')

    def test_edit_budget_invalid_id(self):
        response = self.client.post('/api/budget/edit/', {'budget_id': ''})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Invalid budget ID.')

    def test_delete_budget_invalid_id(self):
        response = self.client.post('/api/budget/delete/', {'budget_id': 'xyz'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Invalid budget ID.')


class SaaSPermissionAndFeatureTest(TestCase):
    def setUp(self):
        # Create different role users
        self.super_admin_user = User.objects.create_user(username='superadmin', password='password123', is_staff=True)
        self.super_admin_user.profile.role = 'super_admin'
        self.super_admin_user.profile.save()

        self.support_staff_user = User.objects.create_user(username='staff', password='password123', is_staff=True)
        self.support_staff_user.profile.role = 'support_staff'
        self.support_staff_user.profile.save()

        self.free_user = User.objects.create_user(username='freeuser', password='password123')
        self.free_user.profile.subscription_tier = 'free'
        self.free_user.profile.save()

        self.business_user = User.objects.create_user(username='bizuser', password='password123')
        self.business_user.profile.subscription_tier = 'business'
        self.business_user.profile.save()

    def test_admin_dashboard_role_permission(self):
        # Free user should get redirected
        self.client.login(username='freeuser', password='password123')
        response = self.client.get('/admin-dashboard/')
        self.assertEqual(response.status_code, 302)

        # Support staff user should access dashboard successfully
        self.client.login(username='staff', password='password123')
        response = self.client.get('/admin-dashboard/')
        self.assertEqual(response.status_code, 200)

    def test_referral_reward_system(self):
        # Setup referral query parameter
        profile = self.free_user.profile
        profile.referral_code = 'TESTREF123'
        profile.save()
        ref_code = 'TESTREF123'

        response = self.client.post(f'/register/?ref={ref_code}', {
            'username': 'referredfriend',
            'email': 'friend@example.com',
            'password': 'friendpassword123',
            'password_confirm': 'friendpassword123'
        })
        self.assertEqual(response.status_code, 302)
        
        # Verify referred friend has premium subscription tier
        friend = User.objects.get(username='referredfriend')
        self.assertEqual(friend.profile.subscription_tier, 'pro')
        self.assertIsNotNone(friend.profile.subscription_end_date)
        
        # Verify referrer has premium subscription tier
        self.free_user.profile.refresh_from_db()
        self.assertEqual(self.free_user.profile.subscription_tier, 'pro')

    def test_business_team_management(self):
        # Login business owner
        self.client.login(username='bizuser', password='password123')
        
        # Create team
        team = Team.objects.create(name="Biz Team", owner=self.business_user)
        
        # Add free user to team
        response = self.client.post('/api/team/add/', {'username': 'freeuser'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify membership
        self.assertTrue(team.members.filter(username='freeuser').exists())
        
        # Remove from team
        response = self.client.post('/api/team/remove/', {'member_id': self.free_user.id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify membership removed
        self.assertFalse(team.members.filter(username='freeuser').exists())

    def test_offline_expense_synchronization(self):
        self.client.login(username='freeuser', password='password123')
        import json
        payload = {
            'expenses': [
                {
                    'category': 'Food',
                    'description': 'Offline Pizza',
                    'amount': '150.00',
                    'expense_date': '2026-06-03'
                },
                {
                    'category': 'Travel',
                    'description': 'Offline Bus',
                    'amount': '25.50',
                    'expense_date': '2026-06-03'
                }
            ]
        }
        response = self.client.post('/api/expense/sync/', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 2)
        
        # Verify expenses were saved to the database
        expenses = Expense.objects.filter(user=self.free_user)
        self.assertEqual(expenses.count(), 2)

    def test_whatsapp_admin_webhook_unauthorized(self):
        # Sending request from an unauthorized number
        response = self.client.post('/api/whatsapp/webhook/', {
            'From': 'whatsapp:+19998887777',
            'Body': 'HELP'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Unauthorized access', response.content.decode('utf-8'))

    def test_whatsapp_admin_webhook_commands(self):
        # Make freeuser have a profile with a username
        # Sending SHOW USERS from authorized number
        response = self.client.post('/api/whatsapp/webhook/', {
            'From': 'whatsapp:+919944550063',
            'Body': 'SHOW USERS'
        })
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('SmartSpend Users', content)
        self.assertIn('freeuser', content)

        # Sending TOTAL EXPENSES
        response = self.client.post('/api/whatsapp/webhook/', {
            'From': 'whatsapp:+919944550063',
            'Body': 'TOTAL EXPENSES'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Platform-Wide Expense Totals', response.content.decode('utf-8'))

        # Sending SERVER STATUS
        response = self.client.post('/api/whatsapp/webhook/', {
            'From': 'whatsapp:+919944550063',
            'Body': 'SERVER STATUS'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Server Status', response.content.decode('utf-8'))

        # Sending BUDGET ALERTS
        response = self.client.post('/api/whatsapp/webhook/', {
            'From': 'whatsapp:+919944550063',
            'Body': 'BUDGET ALERTS'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('budget', response.content.decode('utf-8'))


class Phase3EnterpriseTest(TestCase):
    def setUp(self):
        from datetime import date, timedelta
        self.user = User.objects.create_user(username='enterpriseuser', password='password123')
        self.client.login(username='enterpriseuser', password='password123')
        self.profile = self.user.profile

    def test_multi_currency_formatting(self):
        from expenses.utils import format_currency
        # India (INR) Lakhs/Crores format: 12,34,567.89
        self.assertEqual(format_currency(1234567.89, 'INR', 'en'), '₹12,34,567.89')
        # US (USD): 1,234,567.89
        self.assertEqual(format_currency(1234567.89, 'USD', 'en'), '$1,234,567.89')
        # Europe (EUR): 1.234.567,89
        self.assertEqual(format_currency(1234567.89, 'EUR', 'en'), '1.234.567,89 €')
        
    def test_billing_checkout_and_coupon_deductions(self):
        from datetime import date, timedelta
        from expenses.models import Coupon, SubscriptionPayment
        coupon = Coupon.objects.create(code="WELCOME50", discount_percent=50, expiry_date=date.today() + timedelta(days=10), is_active=True)
        
        # Test validate coupon AJAX endpoint
        response = self.client.post('/api/coupon/validate/', {'code': 'WELCOME50'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['discount_percent'], 50)
        
        # Test simulated checkout payment
        response = self.client.post('/checkout/', {
            'plan': 'pro',
            'billing_cycle': 'monthly',
            'coupon_code': 'WELCOME50',
            'amount': '4.99' # 9.99 with 50% discount
        })
        self.assertEqual(response.status_code, 200)
        
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.subscription_tier, 'pro')
        self.assertTrue(SubscriptionPayment.objects.filter(user=self.user, plan='pro', coupon_used=coupon).exists())

    def test_chatbot_advanced_query_and_forecasting(self):
        from datetime import date
        from decimal import Decimal
        Expense.objects.create(user=self.user, category='Food', description='restaurant', amount=Decimal('500.00'), expense_date=date.today())
        Expense.objects.create(user=self.user, category='Travel', description='taxi', amount=Decimal('200.00'), expense_date=date.today())
        Expense.objects.create(user=self.user, category='Bills', description='electricity', amount=Decimal('100.00'), expense_date=date.today())
        
        # Test hotspot analysis query
        response = get_chatbot_response(self.user, "Where did I spend most this month?")
        self.assertIn("Food", response)
        
        # Test predictive forecasting query
        response = get_chatbot_response(self.user, "how much will I spend next month?")
        self.assertIn("forecast", response.lower())

    def test_mfa_login_verification_flow(self):
        # Enable MFA
        self.profile.mfa_enabled = True
        self.profile.save()
        self.client.logout()
        
        # Attempt login
        response = self.client.post('/login/', {
            'username': 'enterpriseuser',
            'password': 'password123'
        })
        # Should redirect to OTP verification page
        self.assertEqual(response.status_code, 302)
        self.assertIn('/otp/', response.url)
        
        # Grab generated OTP code from DB
        self.profile.refresh_from_db()
        otp = self.profile.otp_code
        self.assertIsNotNone(otp)
        
        # Verify correct OTP
        response = self.client.post('/otp/', {'otp': otp})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/', response.url)

    def test_gdpr_export_and_purge_deletion(self):
        # Log some budget
        Budget.objects.create(user=self.user, category='Food', limit_amount=1000)
        
        # Test GDPR export endpoint
        response = self.client.get('/api/gdpr/export/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('user_details', data)
        self.assertEqual(data['user_details']['username'], 'enterpriseuser')
        self.assertEqual(len(data['budgets']), 1)
        
        # Test GDPR purge delete endpoint
        response = self.client.post('/api/gdpr/delete/')
        self.assertEqual(response.status_code, 302)
        # Check that user is deleted from DB
        self.assertFalse(User.objects.filter(username='enterpriseuser').exists())


class Phase4AIAndGlobalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='aiuser', password='password123')
        self.client.login(username='aiuser', password='password123')
        
    def test_currency_choices_aud_cad(self):
        choices = [choice[0] for choice in CURRENCY_CHOICES]
        self.assertIn('AUD', choices)
        self.assertIn('CAD', choices)
        
        profile = self.user.profile
        profile.currency = 'AUD'
        profile.save()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.currency, 'AUD')

    def test_expense_agent_categorize_and_duplicates(self):
        from expenses.ai_agents import ExpenseAgent
        self.assertEqual(ExpenseAgent.auto_categorize("I want a large pizza"), 'Food')
        self.assertEqual(ExpenseAgent.auto_categorize("Uber ride to office"), 'Travel')
        self.assertEqual(ExpenseAgent.auto_categorize("Paying apartment rent"), 'Rent')
        
        from datetime import date
        e1 = Expense.objects.create(user=self.user, category='Food', description='Pizza', amount=150.00, expense_date=date.today())
        e2 = Expense.objects.create(user=self.user, category='Food', description='Pizza 2', amount=150.00, expense_date=date.today())
        
        duplicates = ExpenseAgent.detect_duplicates(self.user)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]['original'].expense_id, e1.expense_id)
        self.assertEqual(duplicates[0]['duplicate'].expense_id, e2.expense_id)

    def test_budget_agent_forecasting(self):
        from expenses.ai_agents import BudgetAgent
        from datetime import date
        b = Budget.objects.create(user=self.user, category='Food', limit_amount=100.00)
        e = Expense.objects.create(user=self.user, category='Food', description='Pizza', amount=95.00, expense_date=date.today())
        
        # 1. Spent 95 (within limit but projected > limit) -> Medium Risk
        warnings = BudgetAgent.forecast_budget_status(self.user)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], 'Food')
        self.assertEqual(warnings[0]['risk_level'], 'Medium')
        
        # 2. Spent 105 (exceeding limit) -> High Risk
        e.amount = 105.00
        e.save()
        warnings2 = BudgetAgent.forecast_budget_status(self.user)
        self.assertEqual(warnings2[0]['risk_level'], 'High')

    def test_savings_agent_tips(self):
        from expenses.ai_agents import SavingsAgent
        from datetime import date, timedelta
        
        tips = SavingsAgent.get_savings_tips(self.user)
        self.assertIn("Set a new Savings Challenge", tips[0])
        
        c = SavingsChallenge.objects.create(
            user=self.user,
            title="Buy Car",
            target_amount=1000.00,
            current_amount=200.00,
            end_date=date.today() + timedelta(days=10)
        )
        tips2 = SavingsAgent.get_savings_tips(self.user)
        self.assertTrue(any("Buy Car" in tip for tip in tips2))

    def test_analytics_agent_spending_spikes(self):
        from expenses.ai_agents import AnalyticsAgent
        from datetime import date
        Expense.objects.create(user=self.user, category='Food', description='lunch 1', amount=10.00, expense_date=date.today())
        Expense.objects.create(user=self.user, category='Food', description='lunch 2', amount=12.00, expense_date=date.today())
        Expense.objects.create(user=self.user, category='Food', description='lunch 3', amount=8.00, expense_date=date.today())
        exp_spike = Expense.objects.create(user=self.user, category='Entertainment', description='concert', amount=100.00, expense_date=date.today())
        
        spikes = AnalyticsAgent.detect_spending_spikes(self.user)
        self.assertTrue(len(spikes) >= 1)
        self.assertEqual(spikes[0]['expense_id'], exp_spike.expense_id)

    def test_support_agent_faq(self):
        from expenses.ai_agents import SupportAgent
        res1 = SupportAgent.match_faq("how do i change currency settings?")
        self.assertIn("Settings page", res1)
        res2 = SupportAgent.match_faq("unmatched random string")
        self.assertIn("couldn't find a direct FAQ answer", res2)

    def test_chatbot_advanced_queries(self):
        from datetime import date, timedelta
        # MoM comparison
        Expense.objects.create(user=self.user, category='Food', description='pizza', amount=100.00, expense_date=date.today())
        first_day_last_month = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
        Expense.objects.create(user=self.user, category='Food', description='old pizza', amount=50.00, expense_date=first_day_last_month)
        
        response_mom = get_chatbot_response(self.user, "compare this month with last month")
        self.assertIn("Month-over-Month Spending Comparison", response_mom)
        self.assertIn("100.00", response_mom)
        self.assertIn("50.00", response_mom)

        # Top 10 expenses
        for i in range(12):
            Expense.objects.create(user=self.user, category='Food', description=f'pizza {i}', amount=10.00 + i, expense_date=date.today())
        
        response_top = get_chatbot_response(self.user, "show my top 10 expenses")
        self.assertIn("Top 10 Highest Expenses", response_top)

        # Where can I reduce spending
        response_reduce = get_chatbot_response(self.user, "where can I reduce spending?")
        self.assertIn("Spending Optimization", response_reduce)


class Phase4BusinessTeamTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='teamowner', password='password123')
        self.manager = User.objects.create_user(username='teammanager', password='password123')
        self.employee = User.objects.create_user(username='teamemployee', password='password123')
        self.other_user = User.objects.create_user(username='otheruser', password='password123')
        
        # Create team with owner
        self.team = Team.objects.create(name="Enterprise Work", owner=self.owner)
        self.team.members.add(self.manager, self.employee)
        
        # Set roles
        m1 = TeamMembership.objects.get(team=self.team, user=self.manager)
        m1.role = 'manager'
        m1.save()
        
        m2 = TeamMembership.objects.get(team=self.team, user=self.employee)
        m2.role = 'employee'
        m2.save()

    def test_team_workspace_rendering(self):
        self.client.login(username='teamowner', password='password123')
        response = self.client.get('/team/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enterprise Work")

    def test_change_member_role(self):
        self.client.login(username='teamowner', password='password123')
        response = self.client.post('/api/team/change-role/', {
            'member_id': self.employee.id,
            'role': 'manager'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        m = TeamMembership.objects.get(team=self.team, user=self.employee)
        self.assertEqual(m.role, 'manager')

    def test_submit_and_process_team_expense_workflow(self):
        # 1. Employee submits pending expense
        self.client.login(username='teamemployee', password='password123')
        response = self.client.post('/api/team/submit-expense/', {
            'team_id': self.team.team_id,
            'amount': '250.00',
            'category': 'Travel',
            'description': 'Taxi ride',
            'expense_date': '2026-06-03'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertIn('manager approval', response.json()['msg'])
        
        # Verify approval object created in DB with status pending
        approval = TeamExpenseApproval.objects.get(team=self.team, submitted_by=self.employee)
        self.assertEqual(approval.status, 'pending')
        self.assertEqual(approval.amount, Decimal('250.00'))
        
        # Verify employee does NOT have a corresponding Expense record yet
        self.assertFalse(Expense.objects.filter(user=self.employee, category='Travel').exists())

        # 2. Non-member user tries to approve - should fail
        self.client.login(username='otheruser', password='password123')
        response = self.client.post('/api/team/process-expense/', {
            'approval_id': approval.id,
            'action': 'approve'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['success'])

        # 3. Manager approves expense - should succeed
        self.client.login(username='teammanager', password='password123')
        response = self.client.post('/api/team/process-expense/', {
            'approval_id': approval.id,
            'action': 'approve'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Verify approval is approved and Expense is created
        approval.refresh_from_db()
        self.assertEqual(approval.status, 'approved')
        self.assertEqual(approval.approved_by, self.manager)
        
        self.assertTrue(Expense.objects.filter(user=self.employee, category='Travel', amount=Decimal('250.00')).exists())


class Phase4ForumTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='forumuser', password='password123')
        self.client.login(username='forumuser', password='password123')

    def test_forum_pages_and_crud(self):
        # 1. View forum board
        response = self.client.get('/forum/')
        self.assertEqual(response.status_code, 200)

        # 2. Create post
        response = self.client.post('/api/forum/post/create/', {
            'title': 'How to track shared expenses?',
            'content': 'I am trying to figure out how to track shared rent with roomies.'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        post_id = data['post_id']
        
        # 3. View detail page
        response = self.client.get(f'/forum/post/{post_id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "How to track shared expenses?")

        # 4. Add comment
        response = self.client.post('/api/forum/comment/create/', {
            'post_id': post_id,
            'content': 'You can use the new Team Workspace features!'
        })
        self.assertEqual(response.status_code, 200)
        comment_data = response.json()
        self.assertTrue(comment_data['success'])
        self.assertEqual(comment_data['content'], 'You can use the new Team Workspace features!')

        # 5. Upvote post
        response = self.client.post('/api/forum/post/upvote/', {
            'post_id': post_id
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['upvoted'])
        self.assertEqual(response.json()['count'], 1)


class Phase4ExcelAndAutomationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='exceluser', password='password123')
        self.client.login(username='exceluser', password='password123')

    def test_excel_export_endpoint(self):
        # Create some expenses
        from datetime import date
        Expense.objects.create(user=self.user, category='Food', description='lunch', amount=15.00, expense_date=date.today())
        Budget.objects.create(user=self.user, category='Food', limit_amount=150.00)
        
        response = self.client.get('/export/excel/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.ms-excel')
        self.assertIn('smartspend_report_exceluser.xml', response['Content-Disposition'])
        self.assertIn('Workbook', response.content.decode('utf-8'))
        self.assertIn('Expenses', response.content.decode('utf-8'))
        self.assertIn('Budgets', response.content.decode('utf-8'))

    def test_pages_routing(self):
        # Marketplace page
        response = self.client.get('/marketplace/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Marketplace")

        # Mobile preview page
        response = self.client.get('/mobile-preview/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Simulator")

    def test_automations_command_execution(self):
        from django.core.management import call_command
        from expenses.models import SavingsChallenge, Notification
        from datetime import date, timedelta
        
        # 1. Create a savings challenge that is completed
        challenge = SavingsChallenge.objects.create(
            user=self.user,
            title="Emergency Fund",
            target_amount=100.00,
            current_amount=100.00,
            end_date=date.today() + timedelta(days=5),
            is_completed=False
        )
        
        # 2. Create historical expenses to establish average, and a spike expense today
        Expense.objects.create(user=self.user, category='Bills', description='old bill 1', amount=10.00, expense_date=date.today() - timedelta(days=2))
        Expense.objects.create(user=self.user, category='Bills', description='old bill 2', amount=12.00, expense_date=date.today() - timedelta(days=1))
        
        # Spike expense logged today
        Expense.objects.create(user=self.user, category='Bills', description='huge spike', amount=60.00, expense_date=date.today())
        
        # Execute automations command
        call_command('run_automations')
        
        # Verify challenge is marked completed
        challenge.refresh_from_db()
        self.assertTrue(challenge.is_completed)
        
        # Verify notifications created
        notifications = Notification.objects.filter(user=self.user)
        messages = [n.message for n in notifications]
        
        # Should have a milestone notification
        self.assertTrue(any("Milestone Reached" in msg for msg in messages))
        # Should have a spike notification
        self.assertTrue(any("Spending Spike Alert" in msg for msg in messages))


class Phase5LaunchAndScalingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='launchuser', password='password123')
        self.client.login(username='launchuser', password='password123')

    def test_developer_key_rate_limiting(self):
        from expenses.models import DeveloperApiKey
        # Create a mock developer key
        key = DeveloperApiKey.objects.create(
            user=self.user,
            name="test_key",
            key_prefix="12345678",
            secret_key_hash="dummyhash",
            rate_limit=2,
            is_active=True
        )
        
        # Make requests with X-API-Key header
        headers = {'X-API-Key': '12345678secret'}
        
        # 1st request should be fine
        response = self.client.get('/dashboard/', headers=headers, HTTP_X_API_KEY='12345678secret')
        self.assertEqual(response.status_code, 200)
        
        # 2nd request should be fine
        response = self.client.get('/dashboard/', headers=headers, HTTP_X_API_KEY='12345678secret')
        self.assertEqual(response.status_code, 200)
        
        # 3rd request should exceed rate limit (429)
        response = self.client.get('/dashboard/', headers=headers, HTTP_X_API_KEY='12345678secret')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Rate limit exceeded', response.json()['error'])

    def test_subscription_limits_middleware(self):
        from datetime import date
        from expenses.models import Expense, Profile
        
        # Set user subscription tier to free
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.subscription_tier = 'free'
        profile.save()
        
        current_date = date.today()
        
        # Create 15 expenses to hit the limit
        for i in range(15):
            Expense.objects.create(
                user=self.user,
                category='Food',
                description=f'free expense {i}',
                amount=1.00,
                expense_date=current_date
            )
            
        # Post a new expense (16th) which should fail due to limits middleware
        response = self.client.post('/api/expense/add/', {
            'category': 'Food',
            'description': 'the sixteenth expense',
            'amount': 10.00,
            'expense_date': str(current_date)
        })
        
        self.assertEqual(response.status_code, 200)
        res_data = response.json()
        self.assertFalse(res_data['success'])
        self.assertIn('Free Tier Limit Reached', res_data['error'])

    def test_prometheus_metrics_endpoint(self):
        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain; version=0.0.4')
        content = response.content.decode('utf-8')
        self.assertIn('smartspend_users_total', content)
        self.assertIn('smartspend_expenses_total', content)

    def test_seo_sitemap_and_robots(self):
        # Sitemap.xml
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/xml')
        
        # Robots.txt
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('User-agent:', content)
        self.assertIn('Disallow: /admin/', content)




