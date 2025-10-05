#!/usr/bin/env python3
"""
Fix empty mandatory fields in P2P CSV files.
This script fills empty mandatory fields with appropriate default values.
"""
import csv
from pathlib import Path
from datetime import datetime
import uuid
import argparse

DATA_DIR = Path(__file__).resolve().parents[1] / 'data'

# Default values for mandatory fields
DEFAULT_VALUES = {
    'p2p_reconciliations.csv': {
        'period_start': lambda: '2025-01-01T00:00:00',
        'period_end': lambda: '2025-01-31T23:59:59',
        'source': lambda: 'manual',
        'status': lambda: 'pending'
    },
    'p2p_audit_logs.csv': {
        'audit_id': lambda: str(uuid.uuid4()),
        'action': lambda: 'unknown',
        'target_type': lambda: 'unknown',
        'target_id': lambda: str(uuid.uuid4()),
        'at': lambda: datetime.now().isoformat()
    },
    'p2p_documents.csv': {
        'document_id': lambda: str(uuid.uuid4()),
        'owner_type': lambda: 'unknown',
        'owner_id': lambda: str(uuid.uuid4()),
        'doc_type': lambda: 'misc',
        'status': lambda: 'pending'
    },
    'p2p_payouts.csv': {
        'payout_id': lambda: str(uuid.uuid4()),
        'investor_id': lambda: str(uuid.uuid4()),
        'amount_gross': lambda: '0.00',
        'status': lambda: 'pending'
    }
}


def read_csv_safe(file_path):
    """Read CSV file safely handling encoding and parsing issues."""
    if not file_path.exists():
        return [], []

    try:
        with file_path.open(newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            rows = list(reader)
            return fieldnames, rows
    except UnicodeDecodeError:
        # Try with latin-1 encoding if utf-8 fails
        with file_path.open(newline='', encoding='latin-1') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            rows = list(reader)
            return fieldnames, rows


def write_csv_safe(file_path, fieldnames, rows):
    """Write CSV file safely."""
    with file_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def is_empty_value(value):
    """Check if a value is considered empty."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ''
    return False


def fix_empty_mandatory_fields(file_name, fieldnames, rows):
    """Fix empty mandatory fields in the given data."""
    if file_name not in DEFAULT_VALUES:
        return rows, 0

    defaults = DEFAULT_VALUES[file_name]
    fixed_count = 0

    for row in rows:
        for field, default_func in defaults.items():
            if field in fieldnames and is_empty_value(row.get(field)):
                row[field] = default_func()
                fixed_count += 1

    return rows, fixed_count


def main():
    parser = argparse.ArgumentParser(
        description='Fix empty mandatory fields in P2P CSV files')
    parser.add_argument('--file', help='Fix specific CSV file only')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be fixed without making changes')

    args = parser.parse_args()

    # Determine which files to check
    if args.file:
        if args.file in DEFAULT_VALUES:
            files_to_check = [args.file]
        else:
            print(f"❌ No default values defined for: {args.file}")
            print(f"Available files: {', '.join(DEFAULT_VALUES.keys())}")
            return 1
    else:
        files_to_check = DEFAULT_VALUES.keys()

    total_fixed = 0

    # Process each file
    for file_name in files_to_check:
        file_path = DATA_DIR / file_name

        if not file_path.exists():
            print(f"⚠️  File not found: {file_name}")
            continue

        fieldnames, rows = read_csv_safe(file_path)

        if not rows:
            print(f"ℹ️  File is empty: {file_name}")
            continue

        fixed_rows, fixed_count = fix_empty_mandatory_fields(
            file_name, fieldnames, rows)

        if fixed_count > 0:
            if args.dry_run:
                print(
                    f"🔍 {file_name}: Would fix {fixed_count} empty mandatory fields")
            else:
                # Create backup
                backup_path = file_path.with_suffix('.csv.backup')
                file_path.rename(backup_path)

                # Write fixed file
                write_csv_safe(file_path, fieldnames, fixed_rows)
                print(
                    f"✅ {file_name}: Fixed {fixed_count} empty mandatory fields (backup: {backup_path.name})")

            total_fixed += fixed_count
        else:
            print(f"✅ {file_name}: No empty mandatory fields found")

    if args.dry_run:
        print(
            f"\n🔍 DRY RUN: Would fix {total_fixed} empty mandatory fields total")
    else:
        print(f"\n✅ Fixed {total_fixed} empty mandatory fields total")

    return 0


if __name__ == '__main__':
    exit(main())
