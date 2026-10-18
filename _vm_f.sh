cd ~/nse-system
git pull --quiet
source venv/bin/activate
sudo systemctl restart nse-terminal
sleep 4
echo "service: $(systemctl is-active nse-terminal) enabled: $(systemctl is-enabled nse-terminal)"
echo -n "panel_script_refs: "; curl -s http://127.0.0.1:8000/ | grep -c refresh.js
python - <<'PY'
import json, urllib.request
def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8000' + path, timeout=15) as r:
        return json.load(r)
h = get('/api/data/health')
print('health ok:', h.get('ok'), 'max_price:', h.get('max_price_date'),
      'rows:', h.get('prices_rows'),
      'gate_blocked:', (h.get('freshness') or {}).get('blocked'))
print('fyers:', {k: v for k, v in (h.get('fyers') or {}).items() if k != 'token'})
print('scheduler running:', (h.get('scheduler') or {}).get('running'),
      'jobs:', len((h.get('scheduler') or {}).get('jobs') or []))
print('artifacts_today:', h.get('artifacts_today'))
s = get('/api/refresh/status')
print('refresh running:', s.get('running'),
      'last:', (s.get('latest_run') or {}).get('status'),
      'run:', (s.get('latest_run') or {}).get('run_id'))
PY
echo DONE
