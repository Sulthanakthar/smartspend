import os
import sys
import django
import re

sys.path.insert(0, r'c:\Users\Sulthan\OneDrive\Desktop\project2')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartspend_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date
from expenses.models import Expense

def run():
    client = Client()
    user = User.objects.filter(username='testuser').first()
    if not user:
        user = User.objects.create_user('testuser', 'testuser@example.com', 'password123')
    
    Expense.objects.filter(user=user).delete()
    expense = Expense.objects.create(
        user=user,
        category='Food',
        description='Pizza Slice',
        amount=Decimal('120.00'),
        expense_date=date.today()
    )
    
    client.login(username='testuser', password='password123')
    
    # Fetch Dashboard
    response = client.get('/dashboard/')
    html = response.content.decode('utf-8')
    
    # Find button matching openEditModal(this)
    match = re.search(r'<button\s+[^>]*onclick="openEditModal\(this\)"[^>]*>.*?</button>', html, re.DOTALL)
    if match:
        print("\n--- Dashboard Button Block ---")
        print(match.group(0))
    else:
        print("Dashboard button match not found. Finding all buttons with openEditModal:")
        matches = re.findall(r'<button[^>]*openEditModal[^>]*>.*?</button>', html, re.DOTALL)
        for m in matches:
            print(m)
            
    # Fetch History
    response_hist = client.get('/history/')
    html_hist = response_hist.content.decode('utf-8')
    
    match_hist = re.search(r'<button\s+[^>]*onclick="openEditModal\(this\)"[^>]*>.*?</button>', html_hist, re.DOTALL)
    if match_hist:
        print("\n--- History Button Block ---")
        print(match_hist.group(0))
    else:
        print("History button match not found.")

if __name__ == '__main__':
    run()
