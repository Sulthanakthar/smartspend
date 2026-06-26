import os
import sys
import django

# Setup Django Environment
sys.path.insert(0, r'c:\Users\Sulthan\OneDrive\Desktop\project2')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartspend_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from expenses.models import MarketplaceProduct, Vendor, MarketplaceOrder, Expense, Profile
from decimal import Decimal

def verify():
    print("--- 1. Resetting test database state ---")
    MarketplaceOrder.objects.all().delete()
    MarketplaceProduct.objects.all().delete()
    Vendor.objects.all().delete()
    Expense.objects.filter(description__icontains="Marketplace Purchase").delete()
    
    # Ensure our main test user 'sulthan' exists and has a whatsapp number
    user = User.objects.filter(username='sulthan').first()
    if not user:
        user = User.objects.create_user('sulthan', 'mohammedsulthan2004@gmail.com', 'password123')
    
    profile = user.profile
    profile.whatsapp_number = '+919944550063'
    profile.save()
    
    client = Client()
    client.force_login(user)
    
    print("\n--- 2. Fetching Marketplace page (Triggers Auto-seeding) ---")
    response = client.get('/marketplace/')
    print(f"Status Code: {response.status_code}")
    
    products_count = MarketplaceProduct.objects.count()
    vendors_count = Vendor.objects.count()
    print(f"Seeded Products: {products_count}")
    print(f"Seeded Vendors: {vendors_count}")
    
    if products_count == 0 or vendors_count == 0:
        print("[ERROR] Seeding failed.")
        return
    else:
        print("[SUCCESS] Seeding completed successfully.")
        
    # Pick a product
    product = MarketplaceProduct.objects.first()
    print(f"\n--- 3. Testing purchase of product: '{product.name}' (Price: Rs {product.price}) ---")
    
    # Send post request to checkout API
    sys.argv.append('test') # force test mode so twilio client prints a mock sid
    response_order = client.post('/api/marketplace/order/', {'product_id': product.product_id})
    print(f"Checkout Status Code: {response_order.status_code}")
    print(f"Checkout Response: {response_order.json()}")
    
    # Verify Order in DB
    order = MarketplaceOrder.objects.filter(buyer=user, product=product).first()
    if order:
        print(f"[SUCCESS] MarketplaceOrder created (ID: {order.order_id}, Price: {order.price_at_purchase})")
    else:
        print("[ERROR] MarketplaceOrder not found in DB.")
        
    # Verify Expense in DB
    expense = Expense.objects.filter(user=user, category='Shopping', description__contains=product.name).first()
    if expense:
        print(f"[SUCCESS] Expense added to buyer's log (ID: {expense.expense_id}, Amount: {expense.amount})")
    else:
        print("[ERROR] Expense record not found in DB.")
        
if __name__ == '__main__':
    verify()
