#!/usr/bin/env python3
"""
Comprehensive P2P CSV validation and fixing tool.
This script provides a complete solution for checking and fixing P2P CSV data issues.
"""
import argparse
import subprocess
import sys
from pathlib import Path


def run_script(script_name, args=None):
    """Run a script and return its exit code."""
    cmd = [sys.executable, f'scripts/{script_name}']
    if args:
        cmd.extend(args)

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description='P2P CSV validation and fixing toolkit')
    parser.add_argument('action', choices=['check', 'fix', 'preflight', 'all'],
                        help='Action to perform')
    parser.add_argument('--file', help='Specific CSV file to process')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without making changes')

    args = parser.parse_args()

    print("🚀 P2P CSV Validation Toolkit")
    print("=" * 40)

    exit_code = 0

    if args.action in ['check', 'all']:
        print("\n📋 CHECKING MANDATORY FIELDS...")
        check_args = [
            '--verbose'] if not args.file else ['--file', args.file, '--verbose']
        code = run_script('check_empty_mandatory_fields.py', check_args)
        if code != 0:
            exit_code = code

    if args.action in ['fix', 'all']:
        print("\n🔧 FIXING EMPTY MANDATORY FIELDS...")
        fix_args = []
        if args.file:
            fix_args.extend(['--file', args.file])
        if args.dry_run:
            fix_args.append('--dry-run')

        code = run_script('fix_empty_mandatory_fields.py', fix_args)
        if code != 0:
            exit_code = code

    if args.action in ['preflight', 'all']:
        print("\n🔍 RUNNING PREFLIGHT CHECKS...")
        code = run_script('csv_preflight.py')
        if code != 0:
            exit_code = code

    print("\n" + "=" * 40)
    if exit_code == 0:
        print("✅ All checks completed successfully!")
    else:
        print("⚠️  Some issues were found. Check the reports for details.")

    return exit_code


if __name__ == '__main__':
    exit(main())
