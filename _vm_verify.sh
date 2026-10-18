set -e
cd ~/nse-system
echo "=== git pull ==="
git pull
source venv/bin/activate
echo "=== compile ==="
python -m py_compile freshness_gate.py signal_guard.py corporate_actions.py rebuild_raw_history.py purge_stale_artifacts.py fyers_client.py ingest_fyers.py db.py daily_update.py data_audit.py fundamentals_derive.py
echo "COMPILE OK"
echo "=== service ==="
sudo systemctl restart nse-terminal
sleep 3
sudo systemctl is-active nse-terminal
echo "=== freshness gate ==="
python freshness_gate.py check || true
echo "=== audit summary ==="
python data_audit.py --json /tmp/vm_audit.json > /tmp/vm_audit_stdout.txt 2>&1 || true
python - <<'PY'
import json
r = json.load(open('/tmp/vm_audit.json'))
print('tables', r['summary']['tables'], 'by_status', r['summary']['by_status'])
print('prices', {k: r['prices'][k] for k in ('rows', 'symbols', 'max_date', 'stale_days', 'history_buckets', 'last_60d_bar_coverage_pct', 'invalid_ohlc_rows')})
f = r['fundamentals']
print('fund rows', f['rows'], 'dead cols', len(f['dead_columns']), f['dead_columns'][:6])
print('empty tables', r['summary']['empty_tables'])
PY
echo "=== purge dry with 5d lag ==="
python purge_stale_artifacts.py | tail -12
echo "=== rebuild plan ==="
python rebuild_raw_history.py plan | grep -E 'to_rebuild|mixed_pending|estimated|universe|resolved'
echo "=== tests ==="
python -m unittest test_freshness_gate test_signal_guard test_fyers_integration test_corporate_actions test_rebuild_raw_history 2>&1 | tail -3
echo "=== DONE ==="
