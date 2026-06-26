from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Predefined categories for expense tracking
CATEGORY_CHOICES = [
    ('Food', 'Food'),
    ('Travel', 'Travel'),
    ('Rent', 'Rent'),
    ('Bills', 'Bills'),
    ('Shopping', 'Shopping'),
    ('Entertainment', 'Entertainment'),
    ('Health', 'Health'),
    ('Other', 'Other'),
]

# Predefined currency options
CURRENCY_CHOICES = [
    ('INR', '₹ (INR)'),
    ('USD', '$ (USD)'),
    ('EUR', '€ (EUR)'),
    ('GBP', '£ (GBP)'),
    ('JPY', '¥ (JPY)'),
    ('AED', 'د.إ (AED)'),
    ('SGD', 'S$ (SGD)'),
    ('AUD', 'A$ (AUD)'),
    ('CAD', 'C$ (CAD)'),
]

class Profile(models.Model):
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('admin', 'Admin'),
        ('support_staff', 'Support Staff'),
        ('user', 'User'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='INR')
    theme = models.CharField(max_length=10, choices=[('dark', 'Dark'), ('light', 'Light')], default='dark')
    language = models.CharField(max_length=5, default='en') # 'en', 'es', 'fr', 'hi', 'ar'
    timezone = models.CharField(max_length=50, default='UTC')
    mfa_enabled = models.BooleanField(default=False)
    voice_rate = models.FloatField(default=1.0)
    notifications_enabled = models.BooleanField(default=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True) # e.g. "+1234567890"
    subscription_tier = models.CharField(max_length=20, default='free', choices=[('free', 'Free'), ('pro', 'Pro'), ('business', 'Business'), ('enterprise', 'Enterprise')])
    subscription_end_date = models.DateField(null=True, blank=True)
    otp_code = models.CharField(max_length=6, null=True, blank=True)
    otp_expiry = models.DateTimeField(null=True, blank=True)
    streak_count = models.IntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    referral_code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    referred_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='referrals')
    achievements = models.CharField(max_length=500, default='[]')

    class Meta:
        indexes = [
            models.Index(fields=['user', 'subscription_tier']),
        ]


    def __str__(self):
        return f"{self.user.username}'s Profile"

class Expense(models.Model):
    CATEGORY_CHOICES = CATEGORY_CHOICES
    expense_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Other')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField(db_index=True)
    payment_mode = models.CharField(
        max_length=50,
        default='Cash',
        choices=[
            ('Cash', 'Cash'),
            ('GPay', 'Google Pay'),
            ('PhonePe', 'PhonePe'),
            ('NetBanking', 'Net Banking'),
            ('CreditCard', 'Credit Card'),
            ('DebitCard', 'Debit Card')
        ]
    )
    is_auto_parsed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-expense_date', '-expense_id']
        indexes = [
            models.Index(fields=['user', 'expense_date']),
            models.Index(fields=['category']),
        ]


    def __str__(self):
        return f"{self.user.username} - {self.category} - {self.amount} on {self.expense_date}"

class Budget(models.Model):
    budget_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    limit_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ('user', 'category')
        indexes = [
            models.Index(fields=['user', 'category']),
        ]


    def __str__(self):
        return f"{self.user.username} - {self.category} Budget: {self.limit_amount}"

# Django signals to auto-create Profile upon User creation
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
    else:
        Profile.objects.create(user=instance)

class UserActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs', null=True, blank=True)
    action = models.CharField(max_length=255) # e.g. "Login", "Logout", "Added Expense: 450 INR"
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        username = self.user.username if self.user else "Anonymous"
        return f"{username} - {self.action} at {self.timestamp}"

# Django authentication signals for automatic active user logging and WhatsApp alerting
from django.contrib.auth.signals import user_logged_in, user_logged_out

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
        
    UserActivityLog.objects.create(
        user=user,
        action="Logged in successfully",
        ip_address=ip
    )
    
    try:
        from expenses.models import UserDeviceSession
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        UserDeviceSession.objects.create(
            user=user,
            ip_address=ip,
            user_agent=user_agent[:500] if user_agent else 'Unknown'
        )
    except Exception:
        pass

    AdminNotification.objects.create(
        event_type='user_login',
        message=f"User {user.username} logged in successfully. IP: {ip}"
    )
    
    from expenses.whatsapp import send_whatsapp_admin_notification
    send_whatsapp_admin_notification(
        f"🔔 *SmartSpend Admin Alert*:\n"
        f"User *{user.username}* has logged in.\n"
        f"IP Address: {ip}\n"
        f"Time: {user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else 'N/A'}"
    )

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user:
        UserActivityLog.objects.create(
            user=user,
            action="Logged out successfully"
        )
        from expenses.whatsapp import send_whatsapp_admin_notification
        send_whatsapp_admin_notification(
            f"💤 *SmartSpend Admin Alert*:\n"
            f"User *{user.username}* has logged out."
        )

class Notification(models.Model):
    notification_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    status = models.CharField(max_length=20, default='unread', choices=[('unread', 'Unread'), ('read', 'Read')])
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:30]}"

class SavingsChallenge(models.Model):
    challenge_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='savings_challenges')
    title = models.CharField(max_length=100)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    current_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    end_date = models.DateField()
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"Challenge {self.title} for {self.user.username} (Target: {self.target_amount})"

class Team(models.Model):
    team_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_teams')
    members = models.ManyToManyField(User, related_name='teams', blank=True)
    organization = models.ForeignKey('Organization', on_delete=models.SET_NULL, null=True, blank=True, related_name='teams')


    def __str__(self):
        return f"Team {self.name} owned by {self.owner.username}"

class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('resolved', 'Resolved'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    ticket_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    internal_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f"Ticket #{self.ticket_id} - {self.subject} ({self.status})"

class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.IntegerField(default=10)
    expiry_date = models.DateField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} ({self.discount_percent}% off)"

class Feedback(models.Model):
    FEEDBACK_TYPES = [
        ('review', 'User Review'),
        ('feature', 'Feature Request'),
        ('bug', 'Bug Report'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedback_entries')
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES, default='review')
    title = models.CharField(max_length=100)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.feedback_type.upper()}: {self.title} by {self.user.username}"

class SubscriptionPayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscription_payments')
    plan = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    billing_cycle = models.CharField(max_length=10, choices=[('monthly', 'Monthly'), ('annual', 'Annual')])
    payment_date = models.DateTimeField(auto_now_add=True)
    coupon_used = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'payment_date']),
        ]


    def __str__(self):
        return f"{self.user.username} - {self.plan} ({self.billing_cycle}) - {self.amount} on {self.payment_date}"


class TeamMembership(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_memberships')
    role = models.CharField(max_length=20, choices=[('owner', 'Owner'), ('admin', 'Admin'), ('manager', 'Manager'), ('employee', 'Employee')], default='employee')
    is_suspended = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        unique_together = ('team', 'user')

    def __str__(self):
        return f"{self.user.username} is {self.role} in {self.team.name}"


class TeamExpenseApproval(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='expense_approvals')
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submitted_team_expenses')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Other')
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField()
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_team_expenses')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Team Expense Submission - {self.submitted_by.username} ({self.amount}) - Status: {self.status}"


class ForumPost(models.Model):
    post_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_posts')
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    upvotes = models.ManyToManyField(User, related_name='upvoted_posts', blank=True)
    is_approved = models.BooleanField(default=True)
    is_flagged = models.BooleanField(default=False)


    def __str__(self):
        return f"Post #{self.post_id} - {self.title} by {self.user.username}"


class ForumComment(models.Model):
    comment_id = models.AutoField(primary_key=True)
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


    def __str__(self):
        return f"Comment #{self.comment_id} by {self.user.username} on Post #{self.post.post_id}"


from django.db.models.signals import m2m_changed

@receiver(m2m_changed, sender=Team.members.through)
def handle_team_members_change(sender, instance, action, pk_set, **kwargs):
    if action == "post_add":
        # Ensure owner also has a membership
        owner_membership, _ = TeamMembership.objects.get_or_create(team=instance, user=instance.owner, defaults={'role': 'owner'})
        if owner_membership.role != 'owner':
            owner_membership.role = 'owner'
            owner_membership.save()
            
        for user_id in pk_set:
            user = User.objects.get(pk=user_id)
            role = 'owner' if user == instance.owner else 'employee'
            TeamMembership.objects.get_or_create(team=instance, user=user, defaults={'role': role})
    elif action == "post_remove":
        for user_id in pk_set:
            TeamMembership.objects.filter(team=instance, user_id=user_id).delete()


# --- Financial Offers ---
class Offer(models.Model):
    offer_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=[
        ('Credit Cards', 'Credit Cards'),
        ('Insurance', 'Insurance'),
        ('Investments', 'Investments'),
        ('Loans', 'Loans'),
        ('Savings Accounts', 'Savings Accounts')
    ])
    affiliate_link = models.URLField()
    is_active = models.BooleanField(default=True)
    payout_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    impressions = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_clicks(self):
        return self.clicks.count()

    @property
    def total_conversions(self):
        return OfferConversion.objects.filter(click__offer=self).count()

    @property
    def total_revenue(self):
        from decimal import Decimal
        return OfferConversion.objects.filter(click__offer=self).aggregate(
            models.Sum('revenue')
        )['revenue__sum'] or Decimal('0.00')

    @property
    def epc(self):
        from decimal import Decimal
        clicks = self.total_clicks
        if clicks == 0:
            return Decimal('0.00')
        return self.total_revenue / Decimal(clicks)

    @property
    def ctr(self):
        if self.impressions == 0:
            return 0.0
        return (self.total_clicks / self.impressions) * 100.0

    def __str__(self):
        return f"{self.title} ({self.category})"

class OfferClick(models.Model):
    click_id = models.AutoField(primary_key=True)
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='clicks')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='offer_clicks')
    clicked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Click by {self.user.username} on {self.offer.title}"

class OfferConversion(models.Model):
    conversion_id = models.AutoField(primary_key=True)
    click = models.OneToOneField(OfferClick, on_delete=models.CASCADE, related_name='conversion')
    revenue = models.DecimalField(max_digits=10, decimal_places=2)
    converted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Conversion for click #{self.click.click_id} - Rev: {self.revenue}"


# --- Organization and Invitations ---
class Organization(models.Model):
    org_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_organizations')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class TeamInvitation(models.Model):
    invite_id = models.AutoField(primary_key=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=[('admin', 'Admin'), ('manager', 'Manager'), ('employee', 'Employee')], default='employee')
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invitations')
    token = models.CharField(max_length=100, unique=True)
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invite to {self.email} for team {self.team.name}"

class TeamBudget(models.Model):
    team_budget_id = models.AutoField(primary_key=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='budgets')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    limit_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ('team', 'category')

    def __str__(self):
        return f"Team {self.team.name} - {self.category} Budget: {self.limit_amount}"


# --- Support Desk Ticketing Replies & Attachments ---
class TicketReply(models.Model):
    reply_id = models.AutoField(primary_key=True)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='replies')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reply on Ticket #{self.ticket.ticket_id} by {self.user.username}"

class TicketAttachment(models.Model):
    attachment_id = models.AutoField(primary_key=True)
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='ticket_attachments/')
    uploaded_at = models.DateTimeField(auto_now_add=True)


# --- Digital Marketplace Vendors, Products, Reviews ---
class Vendor(models.Model):
    vendor_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')
    company_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5.00) # e.g. 5.00%
    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return self.company_name

class MarketplaceProduct(models.Model):
    product_id = models.AutoField(primary_key=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=50, choices=[
        ('Software', 'Software'),
        ('Consulting', 'Consulting'),
        ('Hardware', 'Hardware'),
        ('Office Supplies', 'Office Supplies'),
        ('Services', 'Services')
    ])
    rating_cache = models.FloatField(default=0.0)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class ProductReview(models.Model):
    review_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(MarketplaceProduct, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=5) # 1 to 5
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MarketplaceOrder(models.Model):
    order_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(MarketplaceProduct, on_delete=models.CASCADE, related_name='orders')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='marketplace_orders')
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='orders')
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)
    purchased_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, 
        choices=[('pending', 'Pending'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], 
        default='completed'
    )

    def __str__(self):
        return f"Order #{self.order_id} - {self.buyer.username} bought {self.product.name}"


# --- Forum Engagement Likes, Bookmarks, Reports ---
class ForumPostLike(models.Model):
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name='post_likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')

class ForumPostBookmark(models.Model):
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name='post_bookmarks')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')

class ForumPostReport(models.Model):
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE, related_name='post_reports')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.TextField()
    is_reviewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


# --- SaaS Subscriptions & Invoice Details ---
class Subscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription_detail')
    plan = models.CharField(max_length=20, default='free') # 'free', 'premium', 'professional', 'enterprise'
    status = models.CharField(max_length=20, default='active') # 'active', 'trialing', 'canceled', 'past_due'
    billing_cycle = models.CharField(max_length=10, choices=[('monthly', 'Monthly'), ('annual', 'Annual')], default='monthly')
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.plan} ({self.status})"

class SubscriptionInvoice(models.Model):
    invoice_number = models.CharField(max_length=100, unique=True)
    payment = models.ForeignKey(SubscriptionPayment, on_delete=models.CASCADE, related_name='invoices')
    pdf_file = models.FileField(upload_to='invoices/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.CharField(max_length=20, choices=[('paid', 'Paid'), ('refunded', 'Refunded'), ('failed', 'Failed')], default='paid')

    def __str__(self):
        return f"Invoice {self.invoice_number} ({self.status})"


# --- SaaS Marketing Blog Posts ---
class BlogPost(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blog_posts')
    content = models.TextField()
    category = models.CharField(max_length=50, choices=[('education', 'Education'), ('case_study', 'Case Study'), ('news', 'News')], default='education')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_published = models.BooleanField(default=True)

    def __str__(self):
        return self.title


# --- Customer CRM & Lead Management ---
class CustomerLead(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    company_name = models.CharField(max_length=100, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.CharField(max_length=20, choices=[
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('proposal', 'Proposal'),
        ('won', 'Won'),
        ('lost', 'Lost')
    ], default='new')

    def __str__(self):
        return f"{self.name} - {self.company_name} ({self.status})"


# --- User Security Auditing & Devices ---
class UserDeviceSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_sessions')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, null=True, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_trusted = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} session on {self.ip_address}"


# --- Platform Operations Auditing & Feature Flags ---
class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    entity_type = models.CharField(max_length=100, blank=True, null=True)
    entity_id = models.IntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user.username if self.user else 'System'} - {self.action} ({self.timestamp})"

class FeatureFlag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_enabled = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Flag {self.name}: {self.is_enabled}"


# --- Developer Access Keys & Web Analytics ---
class DeveloperApiKey(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100)
    key_prefix = models.CharField(max_length=8)
    secret_key_hash = models.CharField(max_length=128)
    rate_limit = models.IntegerField(default=60)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"

class UserEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='events')
    event_name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_name} by {self.user.username if self.user else 'Anonymous'}"


class CouponRedemption(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coupon_redemptions')
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='redemptions')
    redeemed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} redeemed {self.coupon.code}"


class AdminNotification(models.Model):
    EVENT_CHOICES = [
        ('user_registration', 'User Registration'),
        ('user_login', 'User Login'),
        ('failed_login', 'Failed Login'),
        ('password_reset', 'Password Reset'),
        ('expense_creation', 'Expense Creation'),
        ('expense_deletion', 'Expense Deletion'),
        ('budget_change', 'Budget Change'),
        ('support_ticket', 'Support Ticket'),
        ('payment', 'Payment'),
        ('subscription_upgrade', 'Subscription Upgrade'),
        ('team_invite', 'Team Invite'),
        ('marketplace_order', 'Marketplace Order'),
        ('forum_report', 'Forum Report'),
    ]
    event_type = models.CharField(max_length=50, choices=EVENT_CHOICES)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_event_type_display()}] {self.message[:50]}"


