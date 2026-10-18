cd ~/nse-system
while pgrep -f "nse_eod_ingest.py history" > /dev/null; do sleep 15; done
echo "=== rebuild finished ==="
tail -30 data/logs/raw_rebuild.log
source venv/bin/activate
sudo systemctl start nse-terminal
sleep 3
echo "service: $(systemctl is-active nse-terminal)"
echo "=== recompute chain ==="
python refresh_pipeline.py run --trigger post-rebuild > data/logs/post_rebuild_chain.log 2>&1 || true
tail -35 data/logs/post_rebuild_chain.log
echo "=== report ==="
python nse_eod_ingest.py report
echo "=== db facts ==="
python - <<'PY'
import sqlite3
c = sqlite3.connect('data/app.db')
print('prices rows', c.execute('select count(*) from prices_daily').fetchone()[0])
print('max date', c.execute('select max(date) from prices_daily').fetchone()[0])
print('basis', c.execute("select basis, count(*) from price_meta group by basis").fetchall())
print('distinct symbols', c.execute('select count(distinct symbol) from prices_daily').fetchone()[0])
print('technicals latest', c.execute('select count(*) from technicals_daily where date=(select max(date) from technicals_daily)').fetchone()[0])
print('pattern tags today', c.execute("select count(*) from pattern_tags where date=date('now','localtime')").fetchone()[0])
print('top picks today', c.execute("select count(*) from top_picks where date=date('now','localtime')").fetchone()[0])
print('scan today', c.execute("select count(*) from scan_results where scan_date=date('now','localtime')").fetchone()[0])
print('delivery rows', c.execute('select count(*) from delivery_daily').fetchone()[0])
PY
echo FINISHED
