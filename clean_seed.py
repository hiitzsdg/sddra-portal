import re

with open('seed_data.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Strip 'monthly_charge': ..., from SEED_MEMBERSHIP
cleaned_code = re.sub(r"'monthly_charge':\s*[0-9\.]+,?\s*", "", code)

with open('seed_data.py', 'w', encoding='utf-8') as f:
    f.write(cleaned_code)

print("Cleaned seed_data.py successfully!")
