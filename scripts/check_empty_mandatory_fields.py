#!/usr/bin/env python3
"""
Check for empty mandatory fields in P2P CSV files.
This script identifies rows with missing required fields based on Django model definitions.
"""
import csv
from pathlib import Path
from collections import defaultdict
import argparse
from datetime import datetime

DATA_DIR = Path(__file__).resolve().parents[1] / 'data'

# Define mandatory fields based on Django model constraints and actual CSV headers
# Fields without blank=True and null=False are considered mandatory
MANDATORY_FIELDS = {
    'p2p_investors.csv': [
        'investor_id', 'type', 'name', 'document', 'status'
    ],
    'p2p_borrowers.csv': [
        'borrower_id', 'name', 'document'
    ],
    'p2p_wallets.csv': [
        'wallet_id', 'owner_type', 'currency', 'available_balance',
        'blocked_balance', 'status'
    ],
    'p2p_loan_offers.csv': [
        'offer_id', 'borrower_id', 'amount', 'rate', 'term_months', 'status'
    ],
    'p2p_contracts.csv': [
        'contract_id', 'offer_id', 'instrument', 'creditor_type',
        'status', 'principal_amount', 'rate', 'term_months', 'schedule_policy'
    ],
    'p2p_installments.csv': [
        'installment_id', 'contract_id', 'sequence', 'due_date',
        'amount_due', 'principal_component', 'interest_component',
        'fees_component', 'status', 'amount_paid', 'carryover'
    ],
    'p2p_payments.csv': [
        'payment_id', 'installment_id', 'contract_id', 'source',
        'amount', 'paid_at', 'status'
    ],
    'p2p_disbursements.csv': [
        'disbursement_id', 'contract_id', 'method', 'amount', 'status'
    ],
    'p2p_payouts.csv': [
        'payout_id', 'investor_id', 'amount_gross', 'status'  # Using actual field names
    ],
    'p2p_documents.csv': [
        # Using actual field names
        'document_id', 'owner_type', 'owner_id', 'doc_type', 'status'
    ],
    'p2p_audit_logs.csv': [
        'audit_id', 'action', 'target_type', 'target_id', 'at'  # Using actual field names
    ],
    'p2p_consignment_agreements.csv': [
        # Using actual field names
        'consignment_agreement_id', 'borrower_id', 'issuer', 'status'
    ],
    'p2p_kyc_risk.csv': [
        # Using actual field names
        'assessment_id', 'subject_type', 'subject_id', 'provider', 'status'
    ],
    'p2p_ledger_entries.csv': [
        # Using actual field names
        'ledger_entry_id', 'entry_date', 'debit_account', 'credit_account', 'amount', 'currency'
    ],
    'p2p_reconciliations.csv': [
        # Using actual field names
        'reconciliation_id', 'period_start', 'period_end', 'source', 'status'
    ],
    'p2p_webhook_events.csv': [
        # Using actual field names
        'event_id', 'direction', 'event', 'resource_type', 'resource_id', 'processing_status'
    ]
}


def read_csv_with_line_numbers(file_path):
    """Read CSV file and return rows with line numbers."""
    if not file_path.exists():
        return [], []

    with file_path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows_with_lines = []

        # start=2 because header is line 1
        for line_num, row in enumerate(reader, start=2):
            rows_with_lines.append((line_num, row))

    return fieldnames, rows_with_lines


def is_empty_value(value):
    """Check if a value is considered empty."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ''
    return False


def check_mandatory_fields(file_name, fieldnames, rows_with_lines):
    """Check for empty mandatory fields in the given CSV data."""
    if file_name not in MANDATORY_FIELDS:
        return []

    mandatory_fields = MANDATORY_FIELDS[file_name]
    issues = []

    # Check if all mandatory fields exist in the CSV
    missing_columns = [
        field for field in mandatory_fields if field not in fieldnames]
    if missing_columns:
        issues.append({
            'type': 'missing_columns',
            'columns': missing_columns,
            'file': file_name
        })

    # Check for empty values in mandatory fields
    for line_num, row in rows_with_lines:
        for field in mandatory_fields:
            if field in fieldnames:  # Only check if field exists
                value = row.get(field, '')
                if is_empty_value(value):
                    issues.append({
                        'type': 'empty_value',
                        'file': file_name,
                        'line': line_num,
                        'field': field,
                        'row_id': row.get('id', row.get(f'{file_name.split("_")[1]}_id', 'unknown'))
                    })

    return issues


def generate_report(all_issues):
    """Generate a detailed report of all issues found."""
    report_lines = []
    report_lines.append(f"P2P CSV Mandatory Fields Check Report")
    report_lines.append(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 60)
    report_lines.append("")

    # Group issues by type and file
    issues_by_file = defaultdict(lambda: defaultdict(list))
    for issue in all_issues:
        issues_by_file[issue['file']][issue['type']].append(issue)

    total_files_with_issues = len(issues_by_file)
    total_issues = len(all_issues)

    report_lines.append(f"SUMMARY:")
    report_lines.append(f"  Files with issues: {total_files_with_issues}")
    report_lines.append(f"  Total issues found: {total_issues}")
    report_lines.append("")

    if total_issues == 0:
        report_lines.append(
            "✅ No mandatory field issues found in P2P CSV files!")
        return report_lines

    # Detailed breakdown by file
    for file_name in sorted(issues_by_file.keys()):
        file_issues = issues_by_file[file_name]
        file_total = sum(len(issues) for issues in file_issues.values())

        report_lines.append(f"📁 {file_name} ({file_total} issues)")
        report_lines.append("-" * 40)

        # Missing columns
        if 'missing_columns' in file_issues:
            for issue in file_issues['missing_columns']:
                report_lines.append(
                    f"  ❌ MISSING COLUMNS: {', '.join(issue['columns'])}")

        # Empty values
        if 'empty_value' in file_issues:
            empty_issues = file_issues['empty_value']
            report_lines.append(
                f"  🔍 EMPTY MANDATORY FIELDS: {len(empty_issues)} occurrences")

            # Group by field for better readability
            by_field = defaultdict(list)
            for issue in empty_issues:
                by_field[issue['field']].append(issue)

            for field in sorted(by_field.keys()):
                field_issues = by_field[field]
                report_lines.append(
                    f"    • {field}: {len(field_issues)} empty values")

                # Show first 10 line numbers
                lines = [str(issue['line']) for issue in field_issues[:10]]
                if len(field_issues) > 10:
                    lines.append(f"... and {len(field_issues) - 10} more")
                report_lines.append(f"      Lines: {', '.join(lines)}")

        report_lines.append("")

    return report_lines


def main():
    parser = argparse.ArgumentParser(
        description='Check for empty mandatory fields in P2P CSV files')
    parser.add_argument('--file', help='Check specific CSV file only')
    parser.add_argument('--output', default='mandatory_fields_report.txt',
                        help='Output report file (default: mandatory_fields_report.txt)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed output for each issue')

    args = parser.parse_args()

    all_issues = []
    files_checked = 0

    # Determine which files to check
    if args.file:
        if args.file in MANDATORY_FIELDS:
            files_to_check = [args.file]
        else:
            print(f"❌ Unknown file: {args.file}")
            print(f"Available files: {', '.join(MANDATORY_FIELDS.keys())}")
            return 1
    else:
        files_to_check = MANDATORY_FIELDS.keys()

    # Check each file
    for file_name in files_to_check:
        file_path = DATA_DIR / file_name

        if not file_path.exists():
            if args.verbose:
                print(f"⚠️  File not found: {file_name}")
            continue

        fieldnames, rows_with_lines = read_csv_with_line_numbers(file_path)

        if not rows_with_lines:
            if args.verbose:
                print(f"ℹ️  File is empty: {file_name}")
            continue

        issues = check_mandatory_fields(file_name, fieldnames, rows_with_lines)
        all_issues.extend(issues)
        files_checked += 1

        if args.verbose:
            if issues:
                print(f"❌ {file_name}: {len(issues)} issues found")
            else:
                print(f"✅ {file_name}: No issues found")

    # Generate and write report
    report_lines = generate_report(all_issues)

    output_path = Path(args.output)
    with output_path.open('w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    # Print summary
    print(f"\n📊 MANDATORY FIELDS CHECK SUMMARY:")
    print(f"   Files checked: {files_checked}")
    print(f"   Total issues: {len(all_issues)}")
    print(f"   Report saved to: {output_path}")

    if all_issues:
        print(f"\n⚠️  Found {len(all_issues)} mandatory field issues!")
        return 1
    else:
        print(f"\n✅ All mandatory fields are properly filled!")
        return 0


if __name__ == '__main__':
    exit(main())
