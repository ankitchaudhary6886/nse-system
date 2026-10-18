set -e
cd ~/nse-system
echo "=== git pull ==="
git pull
source venv/bin/activate
echo "=== compile ==="
python -m py_compile freshness_gate.py signal_guard.py corporate_actions.py rebuild_raw_history.py purge_stale_artifacts.py fyers_client.py ingest_fyers.py db.py daily_update.py data_audit.py fundamentals_derive.py
echo "COMPILE OK"
echo "=== restart service ==="
sudo systemctl restart nse-terminal
sleep 3
sudo systemctl status nse-terminal --no-pager | head -4
echo "=== freshness gate ==="
python freshness_gate.py check || true
echo "=== audit ==="
python data_audit.py --json /tmp/vm_audit.json | head -50
echo "=== fundamentals derive ==="
python fundamentals_derive.py --apply | tail -18
echo "=== fyers symbol master ==="
python ingest_fyers.py master
echo "=== corporate actions summary ==="
python corporate_actions.py summary
echo "=== purge dry run ==="
python purge_stale_artifacts.py | tail -30
echo "=== rebuild plan ==="
python rebuild_raw_history.py plan | head -30
echo "=== tests ==="
python -m unittest test_freshness_gate test_signal_guard test_fyers_integration test_corporate_actions test_rebuild_raw_history 2>&1 | tail -3
echo "=== DONE ==="
