import re

with open("ROUTED-DETAIL.md", "r", encoding="utf-8") as f:
    content = f.read()

# Replace the single { ... } placeholder in Doc 3 POST /api/v1/sync/push
old_payload = '''        "event_type": "sale",
        "payload": { ... }'''
new_payload = '''        "event_type": "sale",
        "payload": {
          "invoice_number": "STORE-01-INV-202609-0042",
          "net_amount": 1050.00,
          "lines": [{"drug_id": "UUID", "batch_no": "BCH-01", "qty": 10}]
        }'''

if old_payload in content:
    content = content.replace(old_payload, new_payload)
    print("Replaced { ... } placeholder in Doc 3 API push.")
else:
    print("old_payload not matched directly, checking regex...")
    content = re.sub(
        r'"payload":\s*\{\s*\.\.\.\s*\}',
        '''"payload": {
          "invoice_number": "STORE-01-INV-202609-0042",
          "net_amount": 1050.00,
          "lines": [{"drug_id": "UUID", "batch_no": "BCH-01", "qty": 10}]
        }''',
        content
    )

with open("ROUTED-DETAIL.md", "w", encoding="utf-8") as f:
    f.write(content)

print("Saved ROUTED-DETAIL.md successfully.")
