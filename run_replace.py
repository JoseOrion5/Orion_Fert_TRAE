
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_idx = content.find('if not pred:', 96376)
old_text = content[old_idx:]

print(f'Replacing {len(old_text)} chars')

new_code = open('replacement_full.txt', 'r', encoding='utf-8').read()

new_content = content[:old_idx] + new_code

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f'Done! New file size: {len(new_content)}')
