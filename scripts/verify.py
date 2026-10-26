"""Independent Python oracle from original CSVs; no SQL mart used to derive expected values."""
import calendar
import collections
import csv
from datetime import date,timedelta
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def month_add(d,n):
    y,m=divmod(d.year*12+d.month-1+n,12)
    return date(y,m+1,1)

def verify(conn):
    rows=list(csv.DictReader((ROOT/'originals/fact_sales.csv').open()))
    products={int(r['product_key']):r for r in csv.DictReader((ROOT/'originals/dim_products.csv').open())}
    groups=collections.defaultdict(list)
    for r in rows: groups[r['order_number']].append(r)
    orders=[]; excluded=[]; recovered=0
    for key,rs in groups.items():
        dates={r['order_date'] for r in rs if r['order_date']}
        customers={r['customer_key'] for r in rs}
        if len(dates)!=1 or len(customers)!=1: excluded.extend(rs);continue
        recovered+=sum(not r['order_date'] for r in rs)
        orders.append(dict(id=key,date=date.fromisoformat(next(iter(dates))),customer=int(next(iter(customers))),
                           revenue=sum(Decimal(r['sales_amount']) for r in rs),
                           categories={products[int(r['product_key'])]['category'] or 'Unknown' for r in rs}))
    end=max(o['date'] for o in orders)
    clients=collections.defaultdict(list)
    months=collections.defaultdict(list)
    for o in orders: clients[o['customer']].append(o);months[o['date'].replace(day=1)].append(o)
    for v in clients.values():v.sort(key=lambda o:(o['date'],o['id']))
    checks=0
    with conn.cursor() as cur:
        cur.execute('SELECT month,buyers,orders,revenue FROM portfolio.monthly')
        for m,b,n,r in cur.fetchall():
            assert len(months[m])==n and len({o['customer'] for o in months[m]})==b
            assert sum(o['revenue'] for o in months[m])==r;checks+=1
        cur.execute('SELECT customer_key,first_date,second_date,orders,revenue,first_category FROM portfolio.customer_mart')
        for c,f,s,n,r,cat in cur.fetchall():
            v=clients[c];assert f==v[0]['date'] and s==(v[1]['date'] if len(v)>1 else None)
            assert n==len(v) and r==sum(o['revenue'] for o in v)
            assert cat==('Mixed' if len(v[0]['categories'])>1 else next(iter(v[0]['categories'])));checks+=1
        cur.execute('SELECT cohort,month_age,cohort_size,mature,active_buyers,retention FROM portfolio.cohort_retention')
        for cohort,h,n,mature,active,rate in cur.fetchall():
            members=[v for v in clients.values() if v[0]['date'].replace(day=1)==cohort]
            observed=month_add(cohort,h+1)<=end+timedelta(days=1)
            count=sum(any(o['date'].replace(day=1)==month_add(cohort,h) for o in v) for v in members)
            assert n==len(members) and mature==observed
            assert active==(count if observed else None)
            assert rate is None if not observed else abs(float(rate)-count/n)<1e-12;checks+=1
        cur.execute('SELECT days,first_category,eligible,repeated FROM portfolio.repeat_horizons')
        for h,cat,n,k in cur.fetchall():
            v=[v for v in clients.values() if (end-v[0]['date']).days>=h and
               ('Mixed' if len(v[0]['categories'])>1 else next(iter(v[0]['categories'])))==cat]
            assert n==len(v)
            assert k==sum(len(x)>1 and (x[1]['date']-x[0]['date']).days<=h for x in v);checks+=1
        # Independent product-limit calculation, including events before censors at tied days.
        durations=collections.defaultdict(lambda:[0,0])
        for v in clients.values():
            event=len(v)>1; duration=(v[1]['date']-v[0]['date']).days if event else (end-v[0]['date']).days
            durations[duration][int(event)]+=1
        at_risk=len(clients);survival=1.0;expected={}
        for day,(cens,events) in sorted(durations.items()):
            survival*=1-events/at_risk;expected[day]=(at_risk,events,cens,survival);at_risk-=cens+events
        cur.execute('SELECT day,at_risk,events,censored,survival FROM portfolio.km_second_order')
        for day,n,e,c,s in cur.fetchall():
            a=expected[day];assert (n,e,c)==a[:3] and abs(float(s)-a[3])<1e-10;checks+=1
        cur.execute('SELECT first_category,eligible,repeat_31_120,baseline_rate,second_order_aov FROM portfolio.campaign_baseline')
        for cat,n,k,rate,aov in cur.fetchall():
            members=[v for v in clients.values() if (end-v[0]['date']).days>=120
                and (len(v)==1 or (v[1]['date']-v[0]['date']).days>30)
                and ('Mixed' if len(v[0]['categories'])>1 else next(iter(v[0]['categories'])))==cat]
            repeated=[v for v in members if len(v)>1 and (v[1]['date']-v[0]['date']).days<=120]
            assert n==len(members) and k==len(repeated) and abs(float(rate)-k/n)<1e-12
            assert abs(float(aov)-float(sum(v[1]['revenue'] for v in repeated)/k))<1e-9;checks+=1
        cur.execute('SELECT label,buyers,frequency,aov,revenue FROM portfolio.period_metrics')
        for label,b,f,a,r in cur.fetchall():
            if label.isdigit(): start=date(int(label),1,1);stop=date(int(label)+1,1,1)
            else: start=date(int(label[-4:]),1,1);stop=date(int(label[-4:]),1,29)
            period=[o for o in orders if start<=o['date']<stop]
            expected_b=len({o['customer'] for o in period});expected_r=sum(o['revenue'] for o in period)
            assert b==expected_b and r==expected_r
            assert abs(float(f)-len(period)/expected_b)<1e-12 and abs(float(a)-float(expected_r/len(period)))<1e-9;checks+=1
        # Check month-standardized rates independently with common pooled weights.
        cells=collections.defaultdict(list)
        for v in clients.values():
            cohort=v[0]['date'].replace(day=1)
            if date(2013,1,1)<=cohort<=date(2013,6,1):
                cat='Mixed' if len(v[0]['categories'])>1 else next(iter(v[0]['categories']))
                cells[cohort,cat].append(v)
        weights=collections.Counter()
        for (m,cat),v in cells.items(): weights[m]+=len(v)
        total=sum(weights.values())
        cur.execute('SELECT first_category,eligible,standardized_rate FROM portfolio.category_standardized')
        for cat,n,rate in cur.fetchall():
            expected=0;count=0
            for m in weights:
                v=cells[m,cat];count+=len(v)
                expected+=sum(len(x)>1 and (x[1]['date']-x[0]['date']).days<=180 for x in v)/len(v)*weights[m]/total
            assert n==count and abs(float(rate)-expected)<1e-12;checks+=1
    return dict(independent_comparisons=checks,raw_rows=len(rows),raw_orders=len(groups),
        clean_orders=len(orders),clean_customers=len(clients),date_recovered_lines=recovered,
        excluded_lines=len(excluded),excluded_revenue=str(sum(Decimal(r['sales_amount']) for r in excluded)),
        clean_revenue=str(sum(o['revenue'] for o in orders)),
        repeat_customers=sum(len(v)>1 for v in clients.values()),
        same_day_second=sum(len(v)>1 and v[0]['date']==v[1]['date'] for v in clients.values()),
        observation_start=min(o['date'] for o in orders),observation_end=end,sql_checks='passed',python_checks='passed')
