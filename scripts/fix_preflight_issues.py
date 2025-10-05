#!/usr/bin/env python3
"""
Fix preflight issues in the mock CSV data:
- assign wallets to investors when primary_wallet_id is missing
- fill wallet fields with coherent defaults
- fill investor fields with coherent defaults
- add placeholder contracts for disbursements referencing missing contracts
- ensure offers' borrower_ids exist in borrowers (create placeholders if needed)

This script mutates CSV files in-place. Run from repository root.
"""
import csv
from pathlib import Path
from datetime import datetime
import hashlib

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'

FILES = {
    'wallets': 'p2p_wallets.csv',
    'investors': 'p2p_investors.csv',
    'borrowers': 'p2p_borrowers.csv',
    'offers': 'p2p_loan_offers.csv',
    'contracts': 'p2p_contracts.csv',
    'disbursements': 'p2p_disbursements.csv',
}


def read_csv(path: Path):
    if not path.exists():
        return [], []
    with path.open(newline='') as f:
        r = csv.DictReader(f)
        rows = list(r)
        return r.fieldnames or [], rows


def write_csv(path: Path, fieldnames, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            # ensure order
            out = {k: r.get(k, '') for k in fieldnames}
            w.writerow(out)


def now_ts():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def short(idv):
    return (idv or '')[:8]


def choose_offer(contract_id: str, offers: list):
    """Choose an offer deterministically based on contract_id hash"""
    if not offers:
        return ''
    h = hashlib.sha1(contract_id.encode()).hexdigest()
    idx = int(h, 16) % len(offers)
    return offers[idx]


def main():
    # Load files
    wallets_h, wallets = read_csv(DATA / FILES['wallets'])
    investors_h, investors = read_csv(DATA / FILES['investors'])
    borrowers_h, borrowers = read_csv(DATA / FILES['borrowers'])
    offers_h, offers = read_csv(DATA / FILES['offers'])
    contracts_h, contracts = read_csv(DATA / FILES['contracts'])
    disb_h, disbs = read_csv(DATA / FILES['disbursements'])

    # Prepare id sets
    wallet_ids = [w.get('wallet_id', '').strip() for w in wallets]
    wallet_ids = [w for w in wallet_ids if w]
    investor_ids = [i.get('investor_id', '').strip() for i in investors]
    investor_ids = [i for i in investor_ids if i]
    borrower_ids = {b.get('borrower_id', '').strip()
                    for b in borrowers if b.get('borrower_id')}
    contract_ids = {c.get('contract_id', '').strip()
                    for c in contracts if c.get('contract_id')}

    now = now_ts()

    # 1) Assign wallets to investors where primary_wallet_id missing
    # Pair by index: first investor -> first wallet, etc. Prefer wallets that don't have owner_id set.
    unassigned_wallets = [w for w in wallets if not (
        w.get('owner_id') or w.get('owner_type'))]
    uw_iter = iter(unassigned_wallets)
    assigned_count = 0
    for inv in investors:
        pid = (inv.get('primary_wallet_id') or '').strip()
        inv_id = (inv.get('investor_id') or '').strip()
        if not pid and inv_id:
            try:
                w = next(uw_iter)
            except StopIteration:
                # no more unassigned wallets, try any wallet by index mapping
                idx = investor_ids.index(
                    inv_id) if inv_id in investor_ids else None
                if idx is not None and idx < len(wallets):
                    w = wallets[idx]
                else:
                    w = None
            if w:
                wid = w.get('wallet_id') or ''
                inv['primary_wallet_id'] = wid
                # ensure investor basic fields
                if not inv.get('type'):
                    inv['type'] = 'individual'
                if not inv.get('name'):
                    inv['name'] = f'investor-{short(inv_id)}'
                if not inv.get('status'):
                    inv['status'] = 'active'
                if not inv.get('created_at'):
                    inv['created_at'] = now
                inv['updated_at'] = now
                inv['trace_id'] = inv.get('trace_id') or 'preflight-fixed'

                # fill wallet fields
                w['owner_type'] = 'investor'
                w['owner_id'] = inv_id
                w['currency'] = w.get('currency') or 'BRL'
                w['available_balance'] = w.get(
                    'available_balance') or '1000.00'
                w['blocked_balance'] = w.get('blocked_balance') or '0.00'
                w['status'] = w.get('status') or 'active'
                w['external_reference'] = w.get(
                    'external_reference') or 'preflight-fixed'
                w['created_at'] = w.get('created_at') or now
                w['updated_at'] = now
                w['trace_id'] = w.get('trace_id') or 'preflight-fixed'
                assigned_count += 1

    print(f'Assigned {assigned_count} investors to wallets')

    # 2) Add placeholder contracts for disbursements' missing contract_ids
    missing_contracts = set()
    for d in disbs:
        cid = (d.get('contract_id') or d.get('contract') or '').strip()
        if cid and cid not in contract_ids:
            missing_contracts.add(cid)

    created_contracts = 0
    if missing_contracts:
        # ensure we have fieldnames for contracts; if none, create a reasonable set
        if not contracts_h:
            contracts_h = ['contract_id', 'offer_id', 'instrument', 'creditor_type', 'creditor_id', 'ccb_number', 'status', 'principal_amount', 'rate', 'term_months', 'schedule_policy', 'disbursement_policy',
                           'signature_bundle_id', 'document_links', 'debt_key', 'requester_identifier_key', 'signed_at', 'activated_at', 'closed_at', 'created_at', 'updated_at', 'idempotency_key', 'external_reference', 'trace_id']
        for cid in sorted(missing_contracts):
            row = {k: '' for k in contracts_h}
            row['contract_id'] = cid
            row['offer_id'] = ''
            row['instrument'] = 'ccb'
            row['creditor_type'] = 'investor'
            row['status'] = 'created'
            row['principal_amount'] = '0.00'
            row['rate'] = '0.0'
            row['term_months'] = '0'
            row['schedule_policy'] = 'PRICE'
            row['created_at'] = now
            row['updated_at'] = now
            row['external_reference'] = 'preflight-fixed'
            row['trace_id'] = 'preflight-fixed'
            contracts.append(row)
            contract_ids.add(cid)
            created_contracts += 1

    print(
        f'Created {created_contracts} placeholder contracts for disbursements')

    # 3) Ensure offers' borrower_ids exist in borrowers (create placeholders if needed)
    offer_missing = set()
    for o in offers:
        bid = (o.get('borrower_id') or o.get('borrower') or '').strip()
        if bid and bid not in borrower_ids:
            offer_missing.add(bid)

    created_borrowers = 0
    if offer_missing:
        if not borrowers_h:
            borrowers_h = ['borrower_id', 'name', 'document', 'email', 'phone_number', 'kyc_status', 'credit_status',
                           'risk_score', 'consigned_margin', 'consignment_agreement_id', 'created_at', 'updated_at', 'trace_id']
        for bid in sorted(offer_missing):
            row = {k: '' for k in borrowers_h}
            row['borrower_id'] = bid
            row['name'] = f'placeholder-{short(bid)}'
            row['document'] = '00000000000'
            row['email'] = f'placeholder+{short(bid)}@example.local'
            row['created_at'] = now
            row['updated_at'] = now
            row['trace_id'] = 'preflight-fixed'
            borrowers.append(row)
            borrower_ids.add(bid)
            created_borrowers += 1

    print(
        f'Created {created_borrowers} placeholder borrowers referenced by offers')

    # 4) Fix contracts referencing missing offers
    offer_ids = [o.get('offer_id', '').strip()
                 for o in offers if o.get('offer_id')]
    existing_offer_ids = set(offer_ids)
    contracts_fixed = 0
    for contract in contracts:
        contract_offer_id = (contract.get('offer_id') or '').strip()
        contract_id = contract.get('contract_id', '').strip()

        # Check if offer_id is missing or references a non-existent offer
        if not contract_offer_id or contract_offer_id not in existing_offer_ids:
            if contract_id and offer_ids:
                new_offer_id = choose_offer(contract_id, offer_ids)
                contract['offer_id'] = new_offer_id
                contracts_fixed += 1

    print(f'Fixed {contracts_fixed} contracts with missing offer references')

    # 5) Write back CSVs preserving headers
    if wallets_h:
        write_csv(DATA / FILES['wallets'], wallets_h, wallets)
    if investors_h:
        write_csv(DATA / FILES['investors'], investors_h, investors)
    if borrowers_h:
        write_csv(DATA / FILES['borrowers'], borrowers_h, borrowers)
    if contracts_h:
        write_csv(DATA / FILES['contracts'], contracts_h, contracts)

    print('Wrote updated CSVs. Run scripts/csv_preflight.py to regenerate the report.')


if __name__ == '__main__':
    main()
