"""Build reviewed aggregate evidence and transparent campaign scenarios."""
import json, math, re
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'
def load(name):
    rows=json.loads((OUT/f'{name}.json').read_text())
    for row in rows:
        for k,v in row.items():
            if isinstance(v,str) and re.fullmatch(r'-?\d+(\.\d+)?([eE][+-]?\d+)?',v):row[k]=float(v)
    return rows

def main():
    baseline=next(r for r in load('campaign_baseline') if r['first_category']=='Accessories')
    p0=baseline['baseline_rate'];aov=baseline['second_order_aov']
    # Per 1000 contacted customers; one qualifying repeat order. No claimed realized uplift.
    scenarios=[]
    for discount,uplift in [(d,u) for d in [0,.05] for u in [0,.01,.02,.04]]:
        n=1000; margin=.35;contact=.15;fixed=100
        revenue=n*uplift*aov
        cost=n*contact+fixed+n*(p0+uplift)*aov*discount
        profit=revenue*margin-cost
        scenarios.append(dict(uplift_pp=uplift*100,contacts=n,baseline_rate=p0,aov=aov,
          margin=margin,discount=discount,contact_cost=contact,fixed_cost=fixed,
          incremental_orders=n*uplift,incremental_revenue=revenue,total_campaign_cost=cost,
          incremental_profit=profit,roi=profit/cost,
          break_even_pp=100*(contact+fixed/n+p0*aov*discount)/(aov*(margin-discount))))
    (OUT/'scenarios.json').write_text(json.dumps(scenarios,indent=2))
    # Approximate two-sided two-proportion normal sample size; confirm using real baseline pre-launch.
    p1=p0+.02;pb=(p0+p1)/2
    per_arm=math.ceil((1.96*math.sqrt(2*pb*(1-pb))+.841621*math.sqrt(p0*(1-p0)+p1*(1-p1)))**2/.02**2)
    summary={'repeat_observed_rate':json.loads((OUT/'validation.json').read_text())['repeat_customers']/json.loads((OUT/'validation.json').read_text())['clean_customers'],'experiment_per_arm_2pp':per_arm,
      'campaign_baseline':baseline,'scenarios':scenarios,
      'fixed_horizon_totals':[],'km_at_horizons':[]}
    for h in [30,90,180,365]:
        rows=[r for r in load('repeat_horizons') if r['days']==h]
        n=sum(r['eligible'] for r in rows);k=sum(r['repeated'] for r in rows)
        summary['fixed_horizon_totals'].append({'days':h,'eligible':n,'repeated':k,'rate':k/n})
        km=[r for r in load('km_second_order') if r['day']<=h]
        summary['km_at_horizons'].append({'days':h,'km_repeat':km[-1]['cumulative_repeat']})
    km=load('km_second_order');summary['km_median_days']=next((r['day'] for r in km if r['survival']<=.5),None)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    queries={}
    defs={
      'monthly':'Покупатели уникальны внутри месяца. Выручка = покупатели × заказов на покупателя × средний чек. Только полностью наблюдаемые месяцы для сравнения.',
      'monthly_segments':'New: месяц первой наблюдаемой покупки; Returning: более поздний месяц. Категории не пересекаются внутри месяца, но покупателей нельзя складывать между месяцами.',
      'cohort_retention':'Покупка именно в календарном месяце M после месяца первой наблюдаемой покупки. Знаменатель — размер когорты. Незавершённый целевой месяц = NULL, не ноль.',
      'repeat_horizons':'Второй заказ за <=H дней среди клиентов с минимум H днями наблюдения. Mixed — первая корзина с несколькими категориями.',
      'category_standardized':'Возврат за 180 дней, когорты январь–июнь 2013, общие веса когорт по размеру всей базы этого периода. Описательное сравнение, не причинный эффект.',
      'km_second_order':'Kaplan–Meier до второго заказа, правое цензурирование в последнюю наблюдаемую дату. Требует независимого цензурирования; смена ассортимента ограничивает интерпретацию.',
      'scenarios':'Гипотетическая прибыль: N×uplift×AOV×margin − N×contact − fixed − N×(p0+uplift)×AOV×discount. Скидка субсидирует и органические покупки. Не результаты эксперимента.'}
    names=['monthly','monthly_segments','revenue_bridge','cohort_retention','cohort_summary','repeat_horizons','category_standardized','km_second_order','campaign_baseline','campaign_pool','scenarios','january_category']
    for name in names:
        rows=load(name)
        queries[name]={'rows':rows,'source':{'type':'file','label':'Учебный CSV → PostgreSQL','name':name,
          'tables':[f'portfolio.{name}'] if name!='scenarios' else [],
          'files':['fact_sales.csv','dim_products.csv','dim_customers.csv'],
          'url':'https://github.com/yy4zcbmxhx-hash/SQL_report',
          'sql':f'SELECT * FROM portfolio.{name} ORDER BY 1,2;' if name!='scenarios' else '',
          'executedAt':datetime.now(timezone.utc).isoformat(),
          'metricDefinitions':[{'label':name,'definition':defs.get(name,'Рассчитано по единому набору очищенных заказов. Методология и SQL включены в репозиторий.')}],
          'evidenceFlow':[{'title':'Происхождение','detail':'Учебные данные Data With Baraa; продажи и товары совпадают построчно, клиенты совпадают без технического create_date.'},
            {'title':'Обработка','detail':'16 дат восстановлены внутри заказа; 3 строки на сумму 34 исключены; срез 2014-01-29.'}]},
          'methods':[{'language':'text','code':'scripts/summarize.py' if name=='scenarios' else 'sql/01_schema.sql → CSV COPY → sql/02_marts.sql → sql/03_retention.sql → sql/04_checks.sql → sql/05_sensitivity.sql'}]}
    snapshot={'surface':'dashboard','title':'Повторные покупки интернет-магазина','generatedAt':datetime.now(timezone.utc).isoformat(),
      'status':'verified','buildStatus':'creating','filters':[], 'queries':queries}
    (OUT/'dashboard_snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2))
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
