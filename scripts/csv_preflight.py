#!/usr/bin/env python3
"""
CSV preflight: find cross-file missing references for the mock data CSVs
Writes a report to preflight_report.txt and prints a concise summary.
"""
import csv
from pathlib import Path
from collections import defaultdict
import argparse
from datetime import datetime

DATA_DIR = Path(__file__).resolve().parents[1] / 'data'
OUT_PATH = Path.cwd() / 'preflight_report.txt'

CSV_FILES = {
    'wallets': 'p2p_wallets.csv',
    'investors': 'p2p_investors.csv',
    'borrowers': 'p2p_borrowers.csv',
    'agreements': 'p2p_consignment_agreements.csv',
    'kyc': 'p2p_kyc_risk.csv',
    'offers': 'p2p_loan_offers.csv',
    'contracts': 'p2p_contracts.csv',
    'disbursements': 'p2p_disbursements.csv',
    'installments': 'p2p_installments.csv',
    'payments': 'p2p_payments.csv',
    'documents': 'p2p_documents.csv',
}


def read_rows(name):
    path = DATA_DIR / CSV_FILES[name]
    if not path.exists():
        return []
    with path.open(newline='') as f:
        reader = csv.DictReader(f)
        return list(reader)


def collect_ids(rows, key):
    s = set()
    for r in rows:
        v = r.get(key)
        if v:
            s.add(v.strip())
    return s


def find_missing(ref_rows, ref_field_candidates, target_ids):
    """Return list of (line_index, value, field_used) where value not in target_ids"""
    missing = []
    # start=2 approximate CSV line (header is 1)
    for i, r in enumerate(ref_rows, start=2):
        found = False
        for f in ref_field_candidates:
            if f in r and r[f]:
                val = r[f].strip()
                found = True
                if val not in target_ids:
                    missing.append((i, val, f))
                break
        # If none of the candidate fields present, note that as well
        if not found:
            missing.append((i, None, None))
    return missing


def append_row_to_csv(kind, row_dict):
    path = DATA_DIR / CSV_FILES[kind]
    # If file doesn't exist, create with header from keys
    if not path.exists():
        with path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(row_dict.keys()))
            writer.writeheader()
            writer.writerow(row_dict)
        return

    # Use existing headers
    with path.open(newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or list(row_dict.keys())

    # Ensure row contains all fields
    row_out = {k: row_dict.get(k, '') for k in fieldnames}
    with path.open('a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerow(row_out)


def main(create_missing: bool = False):
    rows = {k: read_rows(k) for k in CSV_FILES}

    # Collect ID sets
    wallets_ids = collect_ids(rows['wallets'], 'wallet_id')
    investors_ids = collect_ids(rows['investors'], 'investor_id')
    borrowers_ids = collect_ids(rows['borrowers'], 'borrower_id')
    agreements_ids = collect_ids(
        rows['agreements'], 'consignment_agreement_id')
    offers_ids = collect_ids(rows['offers'], 'offer_id')
    # offers file sometimes uses 'offer' column - include it
    offers_ids |= collect_ids(rows['contracts'], 'offer')  # defensive
    contracts_ids = collect_ids(rows['contracts'], 'contract_id')
    installments_ids = collect_ids(rows['installments'], 'installment_id')

    report_lines = []
    report_lines.append('CSV Preflight report\n')

    # 1) Offers referencing borrowers
    missing_offers_borrowers = find_missing(
        rows['offers'], ['borrower_id', 'borrower'], borrowers_ids)
    report_lines.append(
        f'Offers referencing missing borrowers: {len(missing_offers_borrowers)}')
    for i, val, f in missing_offers_borrowers[:50]:
        report_lines.append(f'  line {i}: field={f} value={val}')

    # 2) Contracts referencing offers
    missing_contracts_offers = find_missing(
        rows['contracts'], ['offer_id', 'offer'], offers_ids)
    report_lines.append(
        f'Contracts referencing missing offers: {len(missing_contracts_offers)}')
    for i, val, f in missing_contracts_offers[:50]:
        report_lines.append(f'  line {i}: field={f} value={val}')

    # 3) Disbursements -> contracts
    missing_disb_contracts = find_missing(
        rows['disbursements'], ['contract_id', 'contract'], contracts_ids)
    report_lines.append(
        f'Disbursements referencing missing contracts: {len(missing_disb_contracts)}')
    for i, val, f in missing_disb_contracts[:50]:
        report_lines.append(f'  line {i}: field={f} value={val}')

    # 4) Installments -> contracts
    missing_inst_contracts = find_missing(
        rows['installments'], ['contract_id', 'contract'], contracts_ids)
    report_lines.append(
        f'Installments referencing missing contracts: {len(missing_inst_contracts)}')
    for i, val, f in missing_inst_contracts[:50]:
        report_lines.append(f'  line {i}: field={f} value={val}')

    # 5) Payments -> installments and contracts
    missing_pay_inst = find_missing(
        rows['payments'], ['installment_id'], installments_ids)
    report_lines.append(
        f'Payments referencing missing installments: {len(missing_pay_inst)}')
    for i, val, f in missing_pay_inst[:50]:
        report_lines.append(f'  line {i}: field={f} value={val}')

    missing_pay_contract = find_missing(
        rows['payments'], ['contract_id'], contracts_ids)
    report_lines.append(
        f'Payments referencing missing contracts: {len(missing_pay_contract)}')
    for i, val, f in missing_pay_contract[:50]:
        report_lines.append(f'  line {i}: field={f} value={val}')

    # 6) Investors -> wallets (primary_wallet_id or primary_wallet)
    missing_inv_wallet = find_missing(
        rows['investors'], ['primary_wallet_id', 'primary_wallet'], wallets_ids)
    report_lines.append(
        f'Investors referencing missing wallets (primary): {len(missing_inv_wallet)}')
    for i, val, f in missing_inv_wallet[:50]:
        report_lines.append(f'  line {i}: field={f} value={val}')

    # 7) Agreements referencing borrowers
    missing_agreements_borrowers = find_missing(
        rows['agreements'], ['borrower_id', 'borrower'], borrowers_ids)
    report_lines.append(
        f'Agreements referencing missing borrowers: {len(missing_agreements_borrowers)}')
    for i, val, f in missing_agreements_borrowers[:50]:
        report_lines.append(f'  line {i}: field={f} value={val}')

    # Totals summary
    report_lines.append('\nSummary of existing ID counts:')
    report_lines.append(f'  wallets: {len(wallets_ids)}')
    report_lines.append(f'  investors: {len(investors_ids)}')
    report_lines.append(f'  borrowers: {len(borrowers_ids)}')
    report_lines.append(f'  agreements: {len(agreements_ids)}')
    report_lines.append(f'  offers (detected): {len(offers_ids)}')
    report_lines.append(f'  contracts: {len(contracts_ids)}')
    report_lines.append(f'  installments: {len(installments_ids)}')

    OUT_PATH.write_text('\n'.join(report_lines))

    print('\n'.join(report_lines[:20]))
    print(f"\nFull report written to: {OUT_PATH}")

    # If create_missing requested, generate placeholder rows for missing
    if create_missing:
        now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        # 1) For offers referencing missing borrowers we create placeholder borrowers
        missing_borrower_ids = {
            val for (_, val, f) in missing_offers_borrowers if val}
        for bid in missing_borrower_ids:
            row = {
                'borrower_id': bid,
                'name': f'placeholder-{bid[:8]}',
                'document': '',
                'email': '',
                'phone_number': '',
                'kyc_status': '',
                'credit_status': '',
                'risk_score': '',
                'consigned_margin': '',
                'consignment_agreement': '',
                'created_at': now,
                'updated_at': now,
                'trace_id': 'preflight-created',
            }
            append_row_to_csv('borrowers', row)
            report_lines.append(f'Created placeholder borrower: {bid}')

        # 2) Create placeholder wallets for investors referencing missing wallets
        missing_wallet_ids = {val for (_, val, f) in missing_inv_wallet if val}
        for wid in missing_wallet_ids:
            row = {
                'wallet_id': wid,
                'owner_type': 'platform',
                'owner_id': '',
                'currency': 'BRL',
                'available_balance': '0.00',
                'blocked_balance': '0.00',
                'status': 'active',
                'external_reference': 'preflight-created',
                'account_key': '',
                'created_at': now,
                'updated_at': now,
                'trace_id': 'preflight-created',
            }
            append_row_to_csv('wallets', row)
            report_lines.append(f'Created placeholder wallet: {wid}')

        # 3) For payments referencing missing contracts/installments, create placeholder contracts and installments
        missing_contract_ids = {
            val for (_, val, f) in missing_pay_contract if val}
        missing_installment_ids = {
            val for (_, val, f) in missing_pay_inst if val}

        for cid in missing_contract_ids:
            row = {
                'contract_id': cid,
                'offer': '',
                'instrument': 'ccb',
                'creditor_type': 'investor',
                'creditor_id': '',
                'ccb_number': '',
                'status': 'created',
                'principal_amount': '0.00',
                'rate': '0.0',
                'term_months': '0',
                'schedule_policy': 'PRICE',
                'disbursement_policy': '',
                'signature_bundle_id': '',
                'document_links': '{}',
                'debt_key': '',
                'requester_identifier_key': '',
                'signed_at': '',
                'activated_at': '',
                'closed_at': '',
                'idempotency_key': '',
                'external_reference': 'preflight-created',
                'created_at': now,
                'updated_at': now,
                'trace_id': 'preflight-created',
            }
            append_row_to_csv('contracts', row)
            report_lines.append(f'Created placeholder contract: {cid}')

        for iid in missing_installment_ids:
            # assign to first missing contract if available otherwise leave contract_id blank
            assigned_cid = next(iter(missing_contract_ids), '')
            row = {
                'installment_id': iid,
                'contract_id': assigned_cid,
                'sequence': '1',
                'due_date': now.split('T')[0],
                'amount_due': '0.00',
                'principal_component': '0.00',
                'interest_component': '0.00',
                'fees_component': '0.00',
                'status': 'pending',
                'amount_paid': '0.00',
                'paid_at': '',
                'carryover': '0.00',
                'installment_key': '',
                'created_at': now,
                'updated_at': now,
            }
            append_row_to_csv('installments', row)
            report_lines.append(
                f'Created placeholder installment: {iid} (contract {assigned_cid})')

        # Save updated report
        OUT_PATH.write_text('\n'.join(report_lines))
        print('\nCreated placeholders and updated report written to:', OUT_PATH)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='CSV preflight and optional placeholder creation')
    parser.add_argument('--create-missing', action='store_true',
                        help='Create placeholder CSV rows for missing referenced IDs')
    args = parser.parse_args()
    main(create_missing=args.create_missing)
