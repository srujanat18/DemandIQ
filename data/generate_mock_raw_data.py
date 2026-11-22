"""
Synthetic Raw Data Generator for DemandIQ
Generates:
1. products_raw.csv
2. customers_raw.csv
3. sales_raw.csv (with intentional dirty records for ETL validation testing)
4. competitors_raw.csv
5. incremental_batch_1.csv (for incremental load testing)
"""
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
import config

random.seed(42)

def generate_products():
    categories = [
        (1, "Electronics", "Devices, gadgets, and accessories"),
        (2, "Home & Kitchen", "Appliances, cookware, and furnishings"),
        (3, "Apparel", "Clothing, shoes, and sportswear"),
        (4, "Health & Wellness", "Supplements, fitness gear, and care"),
        (5, "Office Supplies", "Stationery, desks, and office tech")
    ]
    
    products = [
        (101, "Ultra HD Monitor 27-inch", 1, 180.00, 299.99, 85, 20),
        (102, "Wireless Mechanical Keyboard", 1, 45.00, 89.99, 140, 25),
        (103, "Ergonomic Vertical Mouse", 1, 20.00, 49.99, 110, 15),
        (104, "Noise Cancelling Headphones", 1, 110.00, 199.99, 60, 10),
        (105, "Smart Watch Pro", 1, 95.00, 179.99, 45, 10),
        (201, "Stainless Steel Air Fryer 5L", 2, 40.00, 79.99, 75, 15),
        (202, "Espresso Coffee Machine", 2, 120.00, 249.99, 30, 8),
        (203, "Cast Iron Skillet Set", 2, 28.00, 59.99, 90, 20),
        (204, "Robotic Vacuum Cleaner", 2, 150.00, 299.99, 40, 10),
        (301, "Men's Performance Jacket", 3, 35.00, 85.00, 120, 30),
        (302, "Women's Seamless Yoga Pants", 3, 18.00, 45.00, 200, 40),
        (303, "Waterproof Trail Running Shoes", 3, 42.00, 110.00, 80, 20),
        (401, "Organic Whey Protein 2kg", 4, 25.00, 54.99, 150, 30),
        (402, "Adjustable Dumbbell Set", 4, 85.00, 169.99, 35, 10),
        (501, "Ergonomic High-Back Mesh Chair", 5, 90.00, 219.99, 50, 15),
        (502, "Electric Height-Adjustable Standing Desk", 5, 180.00, 399.99, 25, 5),
    ]
    
    # Save categories
    cat_file = config.RAW_DATA_DIR / "categories_raw.csv"
    with open(cat_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category_id", "category_name", "description"])
        writer.writerows(categories)

    # Save products
    prod_file = config.RAW_DATA_DIR / "products_raw.csv"
    with open(prod_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["product_id", "product_name", "category_id", "cost_price", "list_price", "stock_quantity", "reorder_level"])
        writer.writerows(products)
    
    print(f"[DATA] Generated {len(categories)} categories and {len(products)} products.")
    return products

def generate_customers():
    cities = ["New York", "San Francisco", "Chicago", "Austin", "Seattle", "Boston", "Denver", "Atlanta"]
    segments = ["Consumer", "Corporate", "Wholesale"]
    first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Sam", "Chris", "Casey", "Riley", "Jamie", "Avery",
                   "Dakota", "Reese", "Rowan", "Hayden", "Logan", "Peyton", "Kendall", "Emerson", "Finley", "Harper"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
                  "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]

    customers = []
    for cid in range(1001, 1061):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        name = f"{fn} {ln}"
        email = f"{fn.lower()}.{ln.lower()}{cid}@example.com"
        loc = random.choice(cities)
        seg = random.choices(segments, weights=[0.65, 0.25, 0.10])[0]
        customers.append((cid, name, email, loc, seg))

    cust_file = config.RAW_DATA_DIR / "customers_raw.csv"
    with open(cust_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["customer_id", "customer_name", "email", "location", "segment"])
        writer.writerows(customers)
    
    print(f"[DATA] Generated {len(customers)} customers.")
    return customers

def generate_sales(products, customers, num_records=3000):
    start_date = datetime(2026, 1, 1)
    end_date = datetime(2026, 10, 31)
    days_range = (end_date - start_date).days

    sales = []
    prod_lookup = {p[0]: p for p in products}
    cust_ids = [c[0] for c in customers]
    channels = ["Online", "In-Store", "Distributor"]
    payments = ["Credit Card", "Debit Card", "PayPal", "Bank Transfer"]

    for sale_id in range(1, num_records + 1):
        rand_day = start_date + timedelta(days=random.randint(0, days_range))
        date_str = rand_day.strftime("%Y-%m-%d")
        
        prod_id = random.choice(list(prod_lookup.keys()))
        prod = prod_lookup[prod_id]
        cust_id = random.choice(cust_ids)
        
        # Quantity follows positive discrete distribution
        qty = random.choices([1, 2, 3, 4, 5, 8, 10], weights=[0.50, 0.25, 0.12, 0.06, 0.04, 0.02, 0.01])[0]
        unit_price = prod[4] # list price
        
        # Occasional discount
        discount = random.choices([0.0, 0.05, 0.10, 0.15], weights=[0.70, 0.15, 0.10, 0.05])[0]
        total_amount = round(qty * unit_price * (1 - discount), 2)
        channel = random.choices(channels, weights=[0.65, 0.25, 0.10])[0]
        payment = random.choice(payments)

        sales.append([
            sale_id, date_str, prod_id, cust_id, qty, unit_price, total_amount, discount, payment, channel
        ])

    # Inject deliberate dirty records for Data Engineering quality testing
    print("[DATA] Injecting dirty data for validation testing...")
    
    # 1. Duplicate rows
    for i in range(10):
        dup_row = list(sales[i * 50])
        sales.append(dup_row) # exact duplicate

    # 2. Negative quantity anomalies
    for i in range(5):
        idx = random.randint(100, 500)
        sales[idx][4] = -1 * abs(sales[idx][4]) # Negative quantity
        sales[idx][6] = round(sales[idx][4] * sales[idx][5], 2)

    # 3. Invalid / Negative / Zero prices
    for i in range(4):
        idx = random.randint(600, 900)
        sales[idx][5] = -25.00 # Invalid price
        sales[idx][6] = round(sales[idx][4] * sales[idx][5], 2)

    # 4. Null / Missing fields
    for i in range(6):
        idx = random.randint(1000, 1500)
        sales[idx][8] = "" # Missing payment method

    # 5. Invalid Product IDs (foreign key violation check)
    for i in range(4):
        idx = random.randint(1600, 2000)
        sales[idx][2] = 9999 # Non-existent product ID

    sales_file = config.RAW_DATA_DIR / "sales_raw.csv"
    with open(sales_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sale_id", "transaction_date", "product_id", "customer_id", "quantity", 
                         "unit_price", "total_amount", "discount_pct", "payment_method", "channel"])
        writer.writerows(sales)

    print(f"[DATA] Saved {len(sales)} sales records (including dirty test records) to sales_raw.csv")

    # Also generate an incremental sample batch (records from November 2026)
    inc_sales = []
    nov_start = datetime(2026, 11, 1)
    for inc_id in range(5001, 5201):
        rand_day = nov_start + timedelta(days=random.randint(0, 20))
        date_str = rand_day.strftime("%Y-%m-%d")
        prod_id = random.choice(list(prod_lookup.keys()))
        prod = prod_lookup[prod_id]
        cust_id = random.choice(cust_ids)
        qty = random.randint(1, 4)
        unit_price = prod[4]
        total_amount = round(qty * unit_price, 2)
        inc_sales.append([
            inc_id, date_str, prod_id, cust_id, qty, unit_price, total_amount, 0.0, "Credit Card", "Online"
        ])

    sample_inc_file = config.SAMPLE_DATA_DIR / "incremental_batch_1.csv"
    with open(sample_inc_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["sale_id", "transaction_date", "product_id", "customer_id", "quantity", 
                         "unit_price", "total_amount", "discount_pct", "payment_method", "channel"])
        writer.writerows(inc_sales)

    print(f"[DATA] Saved {len(inc_sales)} incremental sample records to {sample_inc_file}")

def generate_competitors(products):
    competitor_brands = ["AlphaRetail", "ApexMart", "ZenithSupply", "NovaDepot"]
    records = []
    cid = 1
    today = datetime.now().strftime("%Y-%m-%d")

    for prod in products:
        prod_id = prod[0]
        base_price = prod[4]
        for comp in competitor_brands:
            price_variance = random.uniform(-0.15, 0.12)
            comp_price = round(base_price * (1 + price_variance), 2)
            records.append((cid, prod_id, comp, comp_price, today))
            cid += 1

    comp_file = config.RAW_DATA_DIR / "competitors_raw.csv"
    with open(comp_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["competitor_id", "product_id", "competitor_name", "competitor_price", "recorded_date"])
        writer.writerows(records)

    print(f"[DATA] Generated {len(records)} competitor pricing rows.")

if __name__ == "__main__":
    prods = generate_products()
    custs = generate_customers()
    generate_sales(prods, custs, num_records=3000)
    generate_competitors(prods)
    print("[DATA] All mock raw data generated successfully!")
