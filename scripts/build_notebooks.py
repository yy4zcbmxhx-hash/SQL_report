"""Generate two explanatory notebooks with live PostgreSQL queries, then execute them."""
import json, os, sys
from pathlib import Path
import nbformat as nbf
from nbclient import NotebookClient
from nbconvert import HTMLExporter
ROOT=Path(__file__).resolve().parents[1]
md=nbf.v4.new_markdown_cell;code=nbf.v4.new_code_cell
setup='''from pathlib import Path
import os, json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import psycopg2
from decimal import Decimal
ROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()
conn = psycopg2.connect(os.environ.get('DATABASE_URL', ''))
def query(sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        df = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
        for col in df.columns:
            if any(isinstance(v, Decimal) for v in df[col]):
                df[col] = df[col].map(lambda v: float(v) if v is not None else np.nan)
        return df
plt.rcParams.update({'figure.figsize': (10, 4.2), 'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False})
BLUE, GOLD = '#245b78', '#c88a28'
pd.options.display.float_format = '{:,.3f}'.format
query('SELECT * FROM portfolio.settings')'''
nb1=[md('# Выручка и качество данных\n## Краткий результат\nПроект использует учебные данные о продажах интернет-магазина. В 2013 сумма продаж составила **16 349 836** против **5 842 231** в 2012. Рост числа покупателей и частоты перекрывает падение среднего чека. Разложение показывает, как связаны показатели. Причины изменения поведения покупателей требуют отдельного исследования.\n\nПосле восстановления дат внутри заказов: **27 657 заказов, 18 482 клиента, 29 356 216 суммы продаж**. Три строки на 34 исключены. Полный аудит: `docs/audit.md`.\n\n## Контекст и методы\nЦель анализа состоит в том, чтобы выбрать сегмент для повторных продаж и подготовить проверку предложения. PostgreSQL рассчитывает витрины; Python здесь читает результаты и рисует графики. Перед запуском выполни `scripts/run_pipeline.py` с настройками подключения из README.\n\n### Основные допущения\nПоследняя покупка в данных датирована 2014-01-28. Полнота выгрузки требует отдельной проверки. Валюта, возвраты и скидки неизвестны. Когорты строятся по первой покупке в доступной истории. Для расчёта фактической маржи нужно уточнить смысл поля `cost` и состав расходов.'),code(setup),
md('## Данные: единая политика очистки'),code("query('SELECT * FROM portfolio.quality_summary ORDER BY metric')"),
md('16 дат восстанавливаются только по другим строкам того же заказа. Остальные 3 строки остаются в quarantine. Исходные файлы сохранены без изменений. Строка продаж определяется сочетанием заказа и товара. Сначала считаем показатели заказа, затем клиента и месяца.'),
code("query('SELECT reason,count(*) AS lines,sum(sales_amount) AS excluded FROM portfolio.quarantine GROUP BY reason')"),
md('## Результаты: сопоставимые периоды'),code("period = query('SELECT * FROM portfolio.period_metrics ORDER BY start_date,end_date')\nperiod"),
code('''monthly = query('SELECT * FROM portfolio.monthly WHERE full_month ORDER BY month')
fig, axes = plt.subplots(2, 2, figsize=(11, 7))
for ax, key, label in zip(axes.flat, ['revenue','buyers','frequency','aov'], ['Сумма продаж','Покупатели','Заказов на покупателя','Средний чек']):
    ax.plot(pd.to_datetime(monthly.month), monthly[key].astype(float), color=BLUE)
    ax.set_title(label); ax.grid(axis='y', alpha=.2)
fig.suptitle('Полные месяцы: январь 2011 – декабрь 2013'); fig.tight_layout(); plt.show()'''),
md('Нельзя суммировать месячных уникальных покупателей для годового числа: один человек появляется в нескольких месяцах. Годовые B, F и A рассчитаны заново на уровне заказов.'),
code('''segments = query("SELECT * FROM portfolio.monthly_segments WHERE month >= DATE '2011-01-01' AND month < DATE '2014-01-01' ORDER BY month,segment")
p = segments.pivot(index='month',columns='segment',values='revenue').fillna(0).astype(float)
p.index = pd.to_datetime(p.index)
p.plot.area(color=[BLUE,GOLD], figsize=(11,4));plt.ylabel('Сумма продаж');plt.title('New: месяц первой наблюдаемой покупки; Returning: последующие месяцы');plt.tight_layout();plt.show()'''),
md('### Точное разложение изменения выручки\nВ формуле `R = B × F × A` число покупателей обозначено B, количество заказов на покупателя `F = O/B`, средний чек `A = R/O`.\n\nПорядок замены фиксирован: **B → F → A**:\n\n`ΔB = (B₁ − B₀) × F₀ × A₀`,\n`ΔF = B₁ × (F₁ − F₀) × A₀`,\n`ΔA = B₁ × F₁ × (A₁ − A₀)`.\n\nСумма равна `R₁ − R₀`. Взаимодействия распределяются выбранным порядком; при другом порядке вклады будут другими. Разложение описывает арифметическую связь показателей. Для оценки причинного влияния потребовался бы отдельный дизайн исследования.'),
code("bridge = query('SELECT * FROM portfolio.revenue_bridge ORDER BY comparison')\nbridge"),
code('''b=bridge.iloc[0]
values=[float(b.buyers_effect),float(b.frequency_effect),float(b.aov_effect)]
assert abs(sum(values)-float(b.total_change)) < 1e-6
plt.bar(['Покупатели','Частота','Средний чек'],np.array(values)/1e6,color=[BLUE,BLUE,GOLD]);plt.axhline(0,color='#333',lw=.8)
plt.ylabel('Вклад, млн единиц');plt.title('2012 → 2013: сумма вкладов +10,508 млн');plt.tight_layout();plt.show()'''),
md('### Почему январь нельзя объяснять только удержанием\nСравнение 1–28 января с 1–28 января показывает падение **781 891 → 45 642**. В 2014 в этом окне отсутствуют велосипеды. Чтобы объяснить это падение, сначала нужно проверить ассортимент и полноту выгрузки.'),
code("query('SELECT * FROM portfolio.january_category ORDER BY category,year')"),
md('## Независимая проверка'),code("import sys\nsys.path.insert(0,str(ROOT/'scripts'))\nfrom verify import verify\nverify(conn)"),
md('## Вывод\nПо этим данным можно изучить покупки и сравнить возврат клиентов за одинаковый срок. Для расчёта фактической прибыли нужны сведения о затратах, скидках и возвратах. Во втором ноутбуке выберем сегмент для предложения и рассчитаем условия его окупаемости.'),code('conn.close()')]
nb2=[md('# Когорты, второй заказ и проверяемая инициатива\n## Краткий результат\n37,14% покупателей имеют второй заказ за всё доступное наблюдение. Продолжительность наблюдения у этих клиентов различается. На зрелой 180-дневной базе второй заказ сделали **1 342 из 12 503 (10,73%)**.\n\nПредложение: проверить одно сообщение с дополняющими аксессуарами без скидки на 31-й день после первой корзины Accessories, если второго заказа ещё нет. При гипотезе +2 п.п. и указанных ниже затратах сценарная прибыль на 1 000 контактов **+121,49**. Эффект рассылки пока не измерен; расчёт показывает результат заданного сценария.\n\n## Контекст и методы\nРазличаем возврат **именно в месяце M**, накопленную долю вторых заказов **за H дней** и Kaplan–Meier с цензурированием. В Mixed попадают первые корзины с несколькими категориями. Порядок заказов внутри одного дня условный: order_number; таких вторых заказов 8, они считаются возвратом на день 0.\n\n### Допущения\nДанные учебные. Первые покупки до начала наблюдения неизвестны; новые когорты нельзя считать полной историей привлечения. Наблюдение заканчивается общей датой выгрузки. При этом поведение клиентов могло различаться в разные периоды.'),code(setup),
md('## Когорты: календарный M1, M3, M6'),code('''cohort=query('SELECT * FROM portfolio.cohort_retention WHERE month_age IN (1,3,6) ORDER BY cohort,month_age')
p=cohort.pivot(index='cohort',columns='month_age',values='retention').astype(float)
fig,ax=plt.subplots(figsize=(7,11));cmap=plt.get_cmap('Blues').copy();cmap.set_bad('#dddddd')
im=ax.imshow(p.to_numpy()*100,aspect='auto',vmin=0,vmax=15,cmap=cmap)
ax.set_xticks(range(3),['M1','M3','M6']);ax.set_yticks(range(len(p)),[str(x)[:7] for x in p.index],fontsize=8)
for i in range(len(p)):
    for j in range(3):
        v=p.iloc[i,j];ax.text(j,i,'—' if pd.isna(v) else f'{v*100:.1f}',ha='center',va='center',fontsize=7,color='white' if v>.08 else '#222')
fig.colorbar(im,ax=ax,label='Возврат, % (цветовая шкала 0–15%)');ax.set_title('Доля когорты с покупкой именно в месяце M');plt.tight_layout();plt.show()'''),
md('Серые ячейки обозначают периоды, которые ещё нельзя наблюдать полностью. Значение возврата в них остаётся неизвестным. Полноту целевого месяца проверяем по его правой границе. Покупка через 6 месяцев не требует покупок в M1 и M3: retention не обязан убывать.'),
code("query('SELECT * FROM portfolio.cohort_summary ORDER BY month_age')"),
md('Общий профиль M1/M3/M6 использует один и тот же набор 31 когорт (11 414 клиентов), зрелых до M6: 1,95%, 2,30%, 2,83%. Начальная когорта декабря 2010 наблюдается только с 29-го числа и особенно подвержена левому усечению. Ранние нулевые значения и более позднее появление аксессуаров показывают, что состав продаж менялся. Это ограничивает применимость среднего профиля к современному магазину.'),
md('## Второй заказ: фиксированное окно и цензурирование'),code('''repeat=query('SELECT * FROM portfolio.repeat_horizons ORDER BY days,first_category')
r=repeat[repeat.days==180].copy();r['repeat_rate']=r.repeat_rate.astype(float)
r[['first_category','eligible','repeated','repeat_rate']]'''),
code('''fig,ax=plt.subplots();ax.bar(r.first_category,r.repeat_rate*100,color=BLUE)
for i,row in enumerate(r.itertuples()):ax.text(i,row.repeat_rate*100+1,f'n={row.eligible:,}',ha='center')
ax.set_ylim(0,34);ax.set_ylabel('Второй заказ за 180 дней, %');ax.set_title('Второй заказ по категории первой корзины');plt.tight_layout();plt.show()'''),
md('Разные категории представлены в разные периоды. Дополнительная проверка ниже ограничивает базу январём–июнем 2013 и использует одинаковые веса месячных когорт. Это уменьшает календарное смешение, но не устраняет различия в клиентах и товарах. У Bikes лишь 176 клиентов в этом сравнении.'),
code("query('SELECT * FROM portfolio.category_standardized ORDER BY first_category')"),
code('''km=query('SELECT * FROM portfolio.km_second_order ORDER BY day')
view=km[km.day<=365]
plt.step(view.day,view.cumulative_repeat.astype(float)*100,where='post',color=BLUE)
plt.xlabel('Дней после первой наблюдаемой покупки');plt.ylabel('Оценка доли второго заказа, %');plt.title('Kaplan–Meier: административное цензурирование');plt.grid(alpha=.2);plt.tight_layout();plt.show()
query("SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY days_to_second) AS median_among_repeaters FROM portfolio.customer_mart WHERE days_to_second IS NOT NULL")'''),
md('В product-limit оценке каждый день S(t) умножается на (1 − events / at_risk); цензурированные покидают риск после этого дня. Оценка возврата по Kaplan–Meier составляет 11,14% к 180 дням и 30,35% к 365 дням. Метод учитывает доступное наблюдение каждого клиента, поэтому его база отличается от базы фиксированных окон. Медиана только среди вернувшихся смещена отбором; KM-медиана 508 дней также зависит от сильного допущения сопоставимости когорт. Для расчёта кампании используем сегмент клиентов, полностью наблюдаемый в выбранном окне.'),
md('## Инициатива и сценарная окупаемость'),code("query(\"SELECT * FROM portfolio.campaign_baseline WHERE first_category='Accessories'\")"),
md('У 4 329 покупателей первой корзины Accessories, без повтора к 30-му дню и с наблюдением до дня 120, 443 сделали второй заказ в дни 31–120. База **10,23%**, средний чек этих вторых заказов **53,07**. На дату среза найдено 416 клиентов с одной покупкой 30–60 дней назад. Это помогает оценить размер сегмента. Для реальной рассылки дополнительно нужны контакты и согласия.\n\nИнициатива: одно сообщение на день 31 с дополняющими аксессуарами по первой корзине, без скидки. Предполагается, что подходящее дополнение к первой покупке заинтересует клиента. Это предположение проверяется экспериментом. Разница с контрольной группой измеряется по назначению (ITT), включая недоставленные сообщения.'),
code("scenarios=pd.read_json(ROOT/'outputs/scenarios.json')\nscenarios[['discount','uplift_pp','incremental_orders','incremental_revenue','total_campaign_cost','incremental_profit','roi','break_even_pp']]"),
md('Формула дополнительной прибыли:\n\n`N × Δp × A × m − N × c − F − N × (p₀ + Δp) × A × d`.\n\nВ расчёте N=1 000 задаёт число контактов, A=53,07 средний чек, p₀=10,23% историческую конверсию. Маржа m=35%, цена контакта c=0,15, расходы на настройку F=100 и скидка d=0% либо 5% заданы как **допущения**. Расчёт учитывает один второй заказ на клиента. Скидка субсидирует и тех, кто купил бы сам. При +2 п.п. без скидки +121,49, со скидкой 5% −203,12. Пороги окупаемости +1,35 и +3,28 п.п. соответственно.\n\nГлавная неопределённость состоит в том, изменит ли сообщение поведение покупателей. Возможен сценарий, при котором сообщение создаёт расходы и раздражает клиента, не увеличивая число покупок. Инициатива разумна при доступном согласованном канале, актуальном ассортименте и подтверждённой марже.'),
code('''fig,ax=plt.subplots()
for discount,g in scenarios.groupby('discount'):
    ax.plot(g.uplift_pp,g.incremental_profit,marker='o',label='Без скидки' if discount==0 else 'Скидка 5%')
ax.axhline(0,color='#333',lw=.8);ax.set_xlabel('Гипотетический прирост, п.п.');ax.set_ylabel('Дополнительная прибыль');ax.legend();ax.set_title('Прибыль при заданном приросте конверсии');plt.tight_layout();plt.show()'''),
md('## Дизайн эксперимента и решение\nНа 31-й день подходящих клиентов с согласием на контакт случайно распределяют между двумя равными группами. Назначенную группу сохраняют в данных. При распределении учитывают месяц входа и диапазон чека. Группу клиента сохраняют до конца эксперимента; пересекающиеся кампании исключают. Основная метрика показывает долю назначенных клиентов со вторым оплаченным неотменённым заказом в дни 31–120. В расчёте сохраняют всех назначенных клиентов по принципу ITT. Для принятия решения считают дополнительную маржинальную прибыль на назначенного клиента после всех расходов. Также отслеживают возвраты, жалобы, отписки и расходы на скидки. Допустимые пределы этих показателей согласуют до старта.\n\nДля обнаружения +2 п.п. от 10,23%: двустороннее α=5%, мощность 80%, нормальная аппроксимация двух долей даёт **3 913 на группу**. Этот размер выборки рассчитан для конверсии. Для прибыли нужна её дисперсия и отдельный расчёт. 416 текущих кандидатов недостаточно; нужен поток новых когорт. Длительность включает набор нужного числа клиентов и 90 дней наблюдения каждого участника. Точная дата окончания зависит от скорости набора.\n\nДо анализа зафиксировать размер выборки, правила исключений, основную метрику и процедуру. Проверить соответствие размеров групп плану 50/50, повторные назначения и доставку. Не останавливаться при случайном p<0,05. Оценить разность долей с 95% ДИ и прибыль с клиентским bootstrap-интервалом. Расширять кампанию следует при подтверждённом полезном экономическом эффекте и приемлемом уровне побочных последствий. A/B-тест не проводился.\n\n## Что сделано и что нужно защитить\nSQL, проверки, графики и формулировки этой версии подготовлены с помощью ИИ. Самостоятельное владение пользователя не проверялось. Для интервью нужно уметь заново построить orders, объяснить знаменатели, NULL незрелых когорт, сумму вкладов и расходы на скидку для клиентов, которые купили бы сами. См. `docs/interview.md`.'),code('conn.close()')]

if __name__=='__main__':
    kernel=ROOT/'.jupyter/kernels/portfolio';kernel.mkdir(parents=True,exist_ok=True)
    (kernel/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],'display_name':'SQL portfolio','language':'python'}))
    os.environ['JUPYTER_PATH']=str(ROOT/'.jupyter')
    os.environ['JUPYTER_RUNTIME_DIR']=str(ROOT/'.jupyter/runtime')
    os.environ['MPLCONFIGDIR']=str(ROOT/'.matplotlib')
    (ROOT/'.jupyter/runtime').mkdir(exist_ok=True)
    for name,cells in [('01_revenue_and_quality',nb1),('02_retention_and_experiment',nb2)]:
        nb=nbf.v4.new_notebook(cells=cells,metadata={'kernelspec':{'name':'portfolio','display_name':'SQL portfolio','language':'python'}})
        NotebookClient(nb,timeout=180,kernel_name='portfolio',resources={'metadata':{'path':str(ROOT/'notebooks')}}).execute()
        nbf.validate(nb);nbf.write(nb,ROOT/'notebooks'/f'{name}.ipynb')
        html,_=HTMLExporter().from_notebook_node(nb)
        (ROOT/'notebooks'/f'{name}.html').write_text(html)
        print(name,'executed',len(cells),'cells')
