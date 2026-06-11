from data_loader import load_csv

result = load_csv('sample_data.csv', 'Serie A', '2025-2026')
print(f'Added: {result["rows_added"]}, Skipped: {result["rows_skipped"]}, Errors: {len(result["errors"])}')
if result["errors"]:
    print('Errors:', result["errors"][:5])
