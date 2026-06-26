import re

def parse_expense_text(text):
    """
    Parses natural language text into expense components:
    - amount: float
    - category: string
    - description: string
    """
    if not text:
        return 0.0, 'Other', ''

    text_clean = text.lower().strip()
    # Remove commas inside numbers (e.g. 1,500 -> 1500)
    text_clean = re.sub(r'(?<=\d),(?=\d)', '', text_clean)
    
    # 2. Extract amount
    # Matches numbers (integers or decimals), optionally preceded by currency symbols/words
    amount = 0.0
    # Match digit patterns: e.g. "10", "200", "5000.50"
    amount_match = re.search(r'\b\d+(?:\.\d+)?\b', text_clean)
    if amount_match:
        amount = float(amount_match.group(0))
        # Remove the amount from text to avoid matching it in description
        text_clean = text_clean.replace(amount_match.group(0), '', 1)

    # 3. Categorize by keywords
    categories = {
        'Food': ['food', 'tea', 'coffee', 'breakfast', 'lunch', 'dinner', 'restaurant', 'cafe', 'pizza', 'burger', 'grocery', 'groceries', 'snack', 'snacks', 'zomato', 'swiggy', 'starbucks', 'eat', 'eating', 'bakery'],
        'Entertainment': ['entertainment', 'movie', 'movies', 'cinema', 'theater', 'theatre', 'game', 'games', 'gaming', 'playstation', 'xbox', 'concert', 'party', 'beer', 'bar', 'pub', 'club', 'alcohol', 'drink', 'drinks', 'show', 'shows', 'fun'],
        'Travel': ['travel', 'cab', 'taxi', 'uber', 'ola', 'bus', 'train', 'metro', 'flight', 'fuel', 'petrol', 'diesel', 'gas', 'ticket', 'tickets', 'parking', 'bike', 'car', 'fare'],
        'Rent': ['rent', 'room', 'flat', 'house', 'pg', 'hostel', 'lease'],
        'Bills': ['bill', 'bills', 'electricity', 'water', 'internet', 'wifi', 'phone', 'mobile', 'recharge', 'dth', 'subscription', 'netflix', 'spotify', 'youtube', 'amazon prime', 'gas bill', 'utility', 'utilities'],
        'Shopping': ['shopping', 'clothes', 'shirt', 'tshirt', 't-shirt', 'pants', 'jeans', 'dress', 'shoes', 'sneakers', 'amazon', 'flipkart', 'myntra', 'mall', 'watch', 'bag', 'gift', 'gifts'],
        'Health': ['health', 'medicine', 'medicines', 'doctor', 'hospital', 'clinic', 'gym', 'fitness', 'pharmacy', 'medical', 'dentist', 'dental', 'test', 'blood test', 'insurance', 'health insurance']
    }

    detected_category = 'Other'
    matched_keyword = None
    for category, keywords in categories.items():
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_clean):
                detected_category = category
                matched_keyword = keyword
                break
        if detected_category != 'Other':
            break

    # 4. Extract Description
    # Remove common filler words and verbs
    words_to_remove = [
        'spent', 'spent', 'paid', 'bought', 'on', 'for', 'rupees', 'rupee', 'rs', 'dollars', 'dollar', 'in', 'to', 'me', 'i', 'my', 'spend', 'pay', 'buy', 'amount', 'of', 'a', 'an', 'the', 'cost', 'costing', 'costs'
    ]
    
    desc_clean = re.sub(r'\b(' + '|'.join(words_to_remove) + r')\b', '', text, flags=re.IGNORECASE)
    # Remove raw number digits
    desc_clean = re.sub(r'\b\d+(?:\.\d+)?\b', '', desc_clean)
    # Remove currency symbols
    desc_clean = re.sub(r'[\$₹€£¥]', '', desc_clean)
    # Clean whitespace
    desc_clean = re.sub(r'\s+', ' ', desc_clean).strip()
    
    # If description is empty, fallback to the matched keyword or the original text
    if not desc_clean:
        if matched_keyword:
            desc_clean = matched_keyword.capitalize()
        else:
            desc_clean = text.strip()
            
    if len(desc_clean) > 100:
        desc_clean = desc_clean[:97] + "..."

    return amount, detected_category, desc_clean

def parse_bank_sms(text):
    """
    Parses bank or mobile wallet transaction SMS messages.
    Returns: (amount: float, category: string, description: string, payment_mode: string)
    """
    if not text:
        return 0.0, 'Other', '', 'Cash'

    text_lower = text.lower().strip()
    
    # 1. Detect Payment Mode
    payment_mode = 'Cash'
    if 'gpay' in text_lower or 'google pay' in text_lower or 'googlepay' in text_lower:
        payment_mode = 'GPay'
    elif 'phonepe' in text_lower or 'phone pe' in text_lower:
        payment_mode = 'PhonePe'
    elif 'credit card' in text_lower or 'creditcard' in text_lower or 'cc ending' in text_lower:
        payment_mode = 'CreditCard'
    elif 'debit card' in text_lower or 'debitcard' in text_lower or 'dc ending' in text_lower:
        payment_mode = 'DebitCard'
    elif 'debited' in text_lower or 'bank' in text_lower or 'account' in text_lower or 'a/c' in text_lower or 'transfer' in text_lower:
        payment_mode = 'NetBanking'
        
    # 2. Extract Amount
    # Clean commas inside numbers first (e.g. 2,500.00 -> 2500.00)
    cleaned_text = re.sub(r'(?<=\d),(?=\d)', '', text_lower)
    
    # Find amount indicators
    amount = 0.0
    amount_patterns = [
        r'(?:rs\.?|inr|usd|\$)\s*(\d+(?:\.\d+)?)',
        r'debited\s+(?:by|for)?\s*(?:rs\.?|inr)?\s*(\d+(?:\.\d+)?)',
        r'spent\s+(?:by|for)?\s*(?:rs\.?|inr)?\s*(\d+(?:\.\d+)?)',
        r'\b\d+(?:\.\d+)?\b'  # Fallback to any number
    ]
    for pattern in amount_patterns:
        match = re.search(pattern, cleaned_text)
        if match:
            try:
                amount = float(match.group(1) if len(match.groups()) > 0 else match.group(0))
                break
            except ValueError:
                continue

    # 3. Categorize by keywords
    categories = {
        'Food': ['food', 'tea', 'coffee', 'breakfast', 'lunch', 'dinner', 'restaurant', 'cafe', 'pizza', 'burger', 'grocery', 'groceries', 'snack', 'snacks', 'zomato', 'swiggy', 'starbucks', 'eat', 'eating', 'bakery', 'hotel', 'swiggy Instamart', 'blinkit', 'zepto'],
        'Entertainment': ['entertainment', 'movie', 'movies', 'cinema', 'theater', 'theatre', 'game', 'games', 'gaming', 'playstation', 'xbox', 'concert', 'party', 'beer', 'bar', 'pub', 'club', 'alcohol', 'drink', 'drinks', 'show', 'shows', 'fun', 'bookmyshow', 'netflix', 'spotify', 'youtube premium'],
        'Travel': ['travel', 'cab', 'taxi', 'uber', 'ola', 'bus', 'train', 'metro', 'flight', 'fuel', 'petrol', 'diesel', 'gas', 'ticket', 'tickets', 'parking', 'bike', 'car', 'fare', 'irctc', 'makemytrip', 'redbus'],
        'Rent': ['rent', 'room', 'flat', 'house', 'pg', 'hostel', 'lease', 'landlord'],
        'Bills': ['bill', 'bills', 'electricity', 'water', 'internet', 'wifi', 'phone', 'mobile', 'recharge', 'dth', 'subscription', 'netflix', 'spotify', 'youtube', 'amazon prime', 'gas bill', 'utility', 'utilities', 'act fibernet', 'jio', 'airtel', 'vi'],
        'Shopping': ['shopping', 'clothes', 'shirt', 'tshirt', 't-shirt', 'pants', 'jeans', 'dress', 'shoes', 'sneakers', 'amazon', 'flipkart', 'myntra', 'mall', 'watch', 'bag', 'gift', 'gifts', 'supermarket', 'mart'],
        'Health': ['health', 'medicine', 'medicines', 'doctor', 'hospital', 'clinic', 'gym', 'fitness', 'pharmacy', 'medical', 'dentist', 'dental', 'test', 'blood test', 'insurance', 'health insurance', 'pharmeasy', '1mg', 'apollo']
    }

    detected_category = 'Other'
    matched_keyword = None
    for category, keywords in categories.items():
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', cleaned_text):
                detected_category = category
                matched_keyword = keyword
                break
        if detected_category != 'Other':
            break

    # 4. Extract Merchant/Description
    # Find merchant after keywords like "to", "at", "for", "via"
    merchant = ""
    merchant_patterns = [
        r'(?:to|at|for|merchant)\s+([a-zA-Z0-9\s\.\&\-\'\,\#]+)(?:\s+on|\s+via|\s+ending|\b)',
        r'sent\s+(?:to|for)?\s+([a-zA-Z0-9\s\.\&\-\'\,\#]+)(?:\s+via|\s+on|\b)'
    ]
    for pattern in merchant_patterns:
        match = re.search(pattern, text) # Use original text to keep casing
        if match:
            merchant = match.group(1).strip()
            # Clean up trailing words
            merchant = re.split(r'\b(on|via|ending|at|to|for|date|time|ref|ref\.?|upi|txn)\b', merchant, flags=re.IGNORECASE)[0].strip()
            break
            
    if not merchant:
        if matched_keyword:
            merchant = f"Transaction for {matched_keyword.capitalize()}"
        else:
            merchant = f"Bank Transaction ({payment_mode})"

    # Final cleanup of description length
    if len(merchant) > 100:
        merchant = merchant[:97] + "..."

    return amount, detected_category, merchant, payment_mode
