
import re
import os

source_path = r"c:\Users\sapra\Documents\GitHub\CareStance\frontend\templates\landing.html"
target_path = r"c:\Users\sapra\Documents\GitHub\CareStance\frontend\index.html"

with open(source_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove Jinja tags and simplify nav logic for static
content = re.sub(r'{% if user %}.*?{% else %}', '', content, flags=re.DOTALL)
content = re.sub(r'{% endif %}', '', content)
content = re.sub(r'{{.*?}}', '0.1', content) # Placeholder for numeric loop variables

# Specifically clean up the nav again just in case
content = content.replace('Log In', 'Log In')
content = content.replace('Get Started', 'Get Started')

with open(target_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully converted landing.html to static index.html")
