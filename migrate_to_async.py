"""
Migration script: Convert sync db.query() patterns to async SQLAlchemy in main.py.

Strategy:
1. Replace `Depends(get_db)` with `Depends(get_async_db)` in all async route handlers
   (except get_current_user which remains sync with get_db)
2. Replace `db.query(Model).filter(...).first()` → `(await db.execute(select(Model).where(...))).scalars().first()`
3. Replace `db.query(Model).filter(...).all()` → `(await db.execute(select(Model).where(...))).scalars().all()`
4. Replace `db.query(Model).count()` → `(await db.execute(select(func.count()).select_from(Model))).scalar()`
5. Replace `db.query(func.sum(...)).filter(...).scalar()` → aggregate async pattern
6. Replace `db.delete(obj)` → `await db.delete(obj)` (when inside async context)
"""

import re
import sys

INPUT_FILE = r"C:\Users\sapra\Documents\GitHub\NEXTSTEP\app\main.py"
OUTPUT_FILE = r"C:\Users\sapra\Documents\GitHub\NEXTSTEP\app\main.py"
BACKUP_FILE = r"C:\Users\sapra\Documents\GitHub\NEXTSTEP\app\main.py.bak"

with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Backup original
with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Backup saved to {BACKUP_FILE}")

# ─── Step 1: Fix get_current_user - keep it sync with get_db ──────────────────
# Already done: get_current_user uses Session = Depends(get_db)
# We need to make sure async routes use Depends(get_async_db)

# ─── Step 2: Replace Depends(get_db) → Depends(get_async_db) in async routes ──
# The trick: don't touch get_current_user's signature.
# We'll replace db: AsyncSession = Depends(get_db) → db: AsyncSession = Depends(get_async_db)
content = content.replace(
    'db: AsyncSession = Depends(get_db)',
    'db: AsyncSession = Depends(get_async_db)'
)

# Also update any split lines like:
content = content.replace(
    'db: AsyncSession = Depends(get_db),',
    'db: AsyncSession = Depends(get_async_db),'
)

print("Step 1: Replaced Depends(get_db) with Depends(get_async_db) for AsyncSession params")

# ─── Step 3: Convert simple .filter().first() patterns ────────────────────────

# Pattern: result = db.query(Model).filter(Model.col == val).first()
# →        result = (await db.execute(select(Model).where(Model.col == val))).scalars().first()

def convert_query_filter_first(match):
    var_part = match.group(1)    # e.g., "result = " or "user = "
    model = match.group(2)       # e.g., "models.User"
    filter_args = match.group(3) # e.g., "models.User.email == email"
    indent = match.group(0)[:len(match.group(0)) - len(match.group(0).lstrip())]
    return f"{indent}{var_part}(await db.execute(select({model}).where({filter_args}))).scalars().first()"

# ─── Step 4: Process line by line for complex patterns ────────────────────────
lines = content.split('\n')
new_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    stripped = line.rstrip('\r')
    
    # Detect indentation
    indent = len(stripped) - len(stripped.lstrip())
    indent_str = stripped[:indent]
    
    # Pattern 1: var = db.query(Model).filter(cond).first()
    m = re.match(r'^(\s*)([\w.]+\s*=\s*)db\.query\(([^)]+)\)\.filter\((.+)\)\.first\(\)\s*$', stripped)
    if m:
        prefix = m.group(1)
        assignment = m.group(2)
        model = m.group(3)
        filter_cond = m.group(4)
        new_lines.append(f"{prefix}{assignment}(await db.execute(select({model}).where({filter_cond}))).scalars().first()")
        i += 1
        continue
    
    # Pattern 2: var = db.query(Model).filter(cond).all()
    m = re.match(r'^(\s*)([\w.]+\s*=\s*)db\.query\(([^)]+)\)\.filter\((.+)\)\.all\(\)\s*$', stripped)
    if m:
        prefix = m.group(1)
        assignment = m.group(2)
        model = m.group(3)
        filter_cond = m.group(4)
        new_lines.append(f"{prefix}{assignment}(await db.execute(select({model}).where({filter_cond}))).scalars().all()")
        i += 1
        continue
    
    # Pattern 3: var = db.query(Model).all()
    m = re.match(r'^(\s*)([\w.]+\s*=\s*)db\.query\(([^)]+)\)\.all\(\)\s*$', stripped)
    if m:
        prefix = m.group(1)
        assignment = m.group(2)
        model = m.group(3)
        new_lines.append(f"{prefix}{assignment}(await db.execute(select({model}))).scalars().all()")
        i += 1
        continue
    
    # Pattern 4: var = db.query(Model).count()
    m = re.match(r'^(\s*)([\w.]+\s*=\s*)db\.query\(([^)]+)\)\.count\(\)\s*$', stripped)
    if m:
        prefix = m.group(1)
        assignment = m.group(2)
        model = m.group(3)
        new_lines.append(f"{prefix}{assignment}(await db.execute(select(func.count()).select_from({model}))).scalar()")
        i += 1
        continue
    
    # Pattern 5: var = db.query(Model).filter(cond).count()
    m = re.match(r'^(\s*)([\w.]+\s*=\s*)db\.query\(([^)]+)\)\.filter\((.+)\)\.count\(\)\s*$', stripped)
    if m:
        prefix = m.group(1)
        assignment = m.group(2)
        model = m.group(3)
        filter_cond = m.group(4)
        new_lines.append(f"{prefix}{assignment}(await db.execute(select(func.count()).select_from({model}).where({filter_cond}))).scalar()")
        i += 1
        continue
    
    # Pattern 6: var = db.query(Model).filter(cond).order_by(...).all()
    m = re.match(r'^(\s*)([\w.]+\s*=\s*)db\.query\(([^)]+)\)\.filter\((.+)\)\.order_by\((.+)\)\.all\(\)\s*$', stripped)
    if m:
        prefix = m.group(1)
        assignment = m.group(2)
        model = m.group(3)
        filter_cond = m.group(4)
        order_args = m.group(5)
        new_lines.append(f"{prefix}{assignment}(await db.execute(select({model}).where({filter_cond}).order_by({order_args}))).scalars().all()")
        i += 1
        continue
    
    # Pattern 7: var = db.query(Model).order_by(...).all()
    m = re.match(r'^(\s*)([\w.]+\s*=\s*)db\.query\(([^)]+)\)\.order_by\((.+)\)\.all\(\)\s*$', stripped)
    if m:
        prefix = m.group(1)
        assignment = m.group(2)
        model = m.group(3)
        order_args = m.group(4)
        new_lines.append(f"{prefix}{assignment}(await db.execute(select({model}).order_by({order_args}))).scalars().all()")
        i += 1
        continue
    
    # Pattern 8: var = db.query(Model).filter(cond).order_by(...).limit(n).all()
    m = re.match(r'^(\s*)([\w.]+\s*=\s*)db\.query\(([^)]+)\)\.filter\((.+)\)\.order_by\((.+)\)\.limit\((\d+)\)\.all\(\)\s*$', stripped)
    if m:
        prefix = m.group(1)
        assignment = m.group(2)
        model = m.group(3)
        filter_cond = m.group(4)
        order_args = m.group(5)
        limit_n = m.group(6)
        new_lines.append(f"{prefix}{assignment}(await db.execute(select({model}).where({filter_cond}).order_by({order_args}).limit({limit_n}))).scalars().all()")
        i += 1
        continue
    
    # Pattern 9: var = db.query(Model).order_by(...).limit(n).all()
    m = re.match(r'^(\s*)([\w.]+\s*=\s*)db\.query\(([^)]+)\)\.order_by\((.+)\)\.limit\((\d+)\)\.all\(\)\s*$', stripped)
    if m:
        prefix = m.group(1)
        assignment = m.group(2)
        model = m.group(3)
        order_args = m.group(4)
        limit_n = m.group(5)
        new_lines.append(f"{prefix}{assignment}(await db.execute(select({model}).order_by({order_args}).limit({limit_n}))).scalars().all()")
        i += 1
        continue
    
    # Pattern 10: db.delete(obj)  (in async context - add await if missing)
    # This is tricky to detect safely. Skip for now.
    
    new_lines.append(stripped)
    i += 1

content = '\n'.join(new_lines)

# ─── Step 5: Ensure func is imported in routes that use count ─────────────────
# Already imported via `from sqlalchemy import select, and_, or_`
# We need to add `func` to imports
if 'from sqlalchemy import select, and_, or_' in content:
    content = content.replace(
        'from sqlalchemy import select, and_, or_',
        'from sqlalchemy import select, and_, or_, func'
    )
    print("Step 5: Added func to sqlalchemy imports")

# ─── Step 6: Fix get_async_db import ─────────────────────────────────────────
if 'get_async_db' not in content:
    content = content.replace(
        'from .database import AsyncSessionLocal, SessionLocal, engine, get_db',
        'from .database import AsyncSessionLocal, SessionLocal, engine, get_db, get_async_db'
    )
    print("Step 6: Added get_async_db to database imports")

# Write output
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Migration complete! Output written to {OUTPUT_FILE}")
print("Please run: python -m py_compile app/main.py to check for syntax errors")
