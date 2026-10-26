"""Create a dedicated PostgreSQL schema, load immutable CSVs, build and verify marts."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import time
import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]
TABLES = ['settings', 'monthly', 'monthly_segments', 'period_metrics', 'revenue_bridge',
          'monthly_bridge', 'cohort_retention', 'repeat_horizons', 'repeat_by_cohort',
          'km_second_order', 'campaign_baseline', 'campaign_pool', 'category_year', 'first_to_second',
          'category_standardized','january_category','quality_summary','cohort_summary']

def run(rebuild=False):
    # libpq reads PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD or .pgpass. Never log a DSN.
    conn = psycopg2.connect(os.environ.get('DATABASE_URL', ''))
    started = time.perf_counter()
    manifest = json.loads((ROOT/'originals/manifest.json').read_text())
    for name in ['dim_customers.csv', 'dim_products.csv', 'fact_sales.csv']:
        assert hashlib.sha256((ROOT/'originals'/name).read_bytes()).hexdigest() == manifest[name]['sha256'], name
    with conn:
        with conn.cursor() as cur:
            if rebuild:
                cur.execute('DROP SCHEMA IF EXISTS portfolio CASCADE')
            cur.execute((ROOT/'sql/01_schema.sql').read_text())
            for table, filename in [('customers','dim_customers.csv'),('products','dim_products.csv'),('sales_raw','fact_sales.csv')]:
                with (ROOT/'originals'/filename).open() as f:
                    cur.copy_expert(f'COPY portfolio.{table} FROM STDIN WITH (FORMAT CSV, HEADER TRUE)', f)
            for name in ['02_marts.sql','03_retention.sql','04_checks.sql','05_sensitivity.sql']:
                cur.execute((ROOT/'sql'/name).read_text())
    output=ROOT/'outputs'; output.mkdir(exist_ok=True)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for table in TABLES:
            cur.execute(f'SELECT * FROM portfolio.{table} ORDER BY 1,2')
            rows=[dict(r) for r in cur.fetchall()]
            (output/f'{table}.json').write_text(json.dumps(rows,default=str,ensure_ascii=False,indent=2))
            if rows:
                with (output/f'{table}.csv').open('w') as f:
                    w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
        cur.execute('SELECT version() AS postgres_version')
        version=cur.fetchone()['postgres_version']
        cur.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT customer_key,count(*) FROM portfolio.orders WHERE order_date >= DATE \'2013-01-01\' GROUP BY customer_key')
        plan='\n'.join(list(r.values())[0] for r in cur.fetchall())
        (output/'explain.txt').write_text(plan)
    from verify import verify
    checks=verify(conn)
    checks.update(postgres_version=version,elapsed_seconds=round(time.perf_counter()-started,3))
    (output/'validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2,default=str))
    conn.close()
    print(json.dumps(checks,ensure_ascii=False,indent=2,default=str))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--rebuild',action='store_true',help='Replace only schema portfolio in the selected database')
    run(parser.parse_args().rebuild)
