import time
import os
from datetime import datetime
from django.db import connection
from django.conf import settings
from django.http import JsonResponse, HttpResponseForbidden
from django.utils.timezone import now
from expenses.models import Expense, Profile, DeveloperApiKey

class DBQueryProfilingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        slow_queries = []
        
        def profile_wrapper(execute, sql, params, many, context):
            start = time.time()
            try:
                return execute(sql, params, many, context)
            finally:
                duration = time.time() - start
                if duration >= 0.100: # 100ms
                    # Log slow query
                    log_file = os.path.join(settings.BASE_DIR, 'slow_queries.log')
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    try:
                        with open(log_file, 'a', encoding='utf-8') as f:
                            f.write(f"[{timestamp}] {request.path} | {duration*1000:.2f}ms | SQL: {sql} | PARAMS: {params}\n")
                    except Exception:
                        pass
        
        with connection.execute_wrapper(profile_wrapper):
            response = self.get_response(request)
            
        return response


class SubscriptionLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Enforce limits on expense logging for Free Tier
        if request.user.is_authenticated and request.path == '/api/expense/add/' and request.method == 'POST':
            profile, _ = Profile.objects.get_or_create(user=request.user)
            if profile.subscription_tier == 'free':
                # Limit free tier to 15 expenses per calendar month
                current_month = now().month
                current_year = now().year
                count = Expense.objects.filter(
                    user=request.user,
                    expense_date__month=current_month,
                    expense_date__year=current_year
                ).count()
                
                if count >= 15:
                    return JsonResponse({
                        'success': False,
                        'error': '🔒 Free Tier Limit Reached: You have reached the monthly limit of 15 expenses. Please upgrade to Pro for unlimited expense tracking.'
                    })
                    
        return self.get_response(request)


class DeveloperApiKeyRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Rate limit based on developer API Key
        api_key = request.headers.get('X-API-Key')
        if api_key:
            # Simple simulation: let's verify key prefix (e.g. prefix is first 8 characters)
            prefix = api_key[:8]
            dev_key = DeveloperApiKey.objects.filter(key_prefix=prefix, is_active=True).first()
            if not dev_key:
                return JsonResponse({'error': 'Invalid API Key'}, status=401)
                
            # Rate limit tracking: store in request or session (simulated memory cache)
            # Limit is key.rate_limit (requests/minute)
            # For simplicity, we use the user's session cache to rate limit API requests
            if not request.session.get('api_rate_limits'):
                request.session['api_rate_limits'] = {}
                
            now_timestamp = int(time.time())
            minute_bucket = now_timestamp // 60
            
            rate_limits = request.session['api_rate_limits']
            key_bucket = f"{prefix}_{minute_bucket}"
            
            requests_this_minute = rate_limits.get(key_bucket, 0)
            if requests_this_minute >= dev_key.rate_limit:
                return JsonResponse({'error': 'Rate limit exceeded. Too many requests.'}, status=429)
                
            rate_limits[key_bucket] = requests_this_minute + 1
            request.session['api_rate_limits'] = rate_limits
            
            # Attach developer key user to the request as api_user for access inside views
            request.api_user = dev_key.user
            
        return self.get_response(request)
