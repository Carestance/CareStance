import re

with open('app/main.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Fix corrupted patterns from bulk replacement
content = re.sub(r'\blocal_await\s+', '', content)
content = re.sub(r'\bsome_await\s+', '', content)
content = re.sub(r'\bawait\s+await\s+', 'await ', content)

# Fix any "awaitawait" without space
content = content.replace('awaitawait', 'await ')

with open('app/main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Fixed async syntax issues")
