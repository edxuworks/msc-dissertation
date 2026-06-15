#!/usr/bin/env bash
cd /home/edwardxu/MSc_Project
source .venv/bin/activate
python3 scripts/corpus_audit.py > data/corpus_audit/audit_run.log 2>&1
echo "Exit code: $?" >> data/corpus_audit/audit_run.log
