"""Reproducible four-page analytical memo from verified PostgreSQL exports."""
from pathlib import Path
import json,os
ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,PageBreak
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT
OUT=ROOT/'outputs'; FIG=OUT/'figures';FIG.mkdir(exist_ok=True)
font=Path(matplotlib.get_data_path())/'fonts/ttf'
pdfmetrics.registerFont(TTFont('DV',str(font/'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('DV-Bold',str(font/'DejaVuSans-Bold.ttf')))
pdfmetrics.registerFontFamily('DV',normal='DV',bold='DV-Bold')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
BLUE='#245b78'; GOLD='#c88a28'
def data(n):return pd.read_json(OUT/f'{n}.json')
m=data('monthly');m=m[m.full_month];fig,ax=plt.subplots(figsize=(9,3))
ax.plot(pd.to_datetime(m.month),m.revenue/1e6,color=BLUE,lw=2)
ax.set_ylabel('Сумма продаж, млн');ax.set_title('Полные месяцы 2011–2013');ax.grid(axis='y',alpha=.2)
fig.tight_layout();fig.savefig(FIG/'monthly.png',dpi=180);plt.close(fig)
r=data('repeat_horizons');r=r[r.days==180];fig,ax=plt.subplots(figsize=(9,3))
ax.bar(r.first_category,r.repeat_rate*100,color=BLUE)
for i,row in enumerate(r.itertuples()):ax.text(i,row.repeat_rate*100+1,f'{row.repeat_rate*100:.1f}%\nn={row.eligible:,}',ha='center',fontsize=9)
ax.set_ylim(0,36);ax.set_ylabel('Второй заказ за 180 дней, %');ax.grid(axis='y',alpha=.15)
fig.tight_layout();fig.savefig(FIG/'repeat.png',dpi=180);plt.close(fig)
s=data('scenarios');fig,ax=plt.subplots(figsize=(9,3))
for d,g in s.groupby('discount'):ax.plot(g.uplift_pp,g.incremental_profit,marker='o',color=BLUE if d==0 else GOLD,label='Без скидки' if d==0 else 'Скидка 5%')
ax.axhline(0,color='#333',lw=.8);ax.set_xlabel('Гипотетический прирост конверсии, п.п.');ax.set_ylabel('Дополнительная прибыль');ax.legend();fig.tight_layout();fig.savefig(FIG/'scenario.png',dpi=180);plt.close(fig)
styles=getSampleStyleSheet()
for name in ['Normal','BodyText','Heading1','Heading2','Title']:styles[name].fontName='DV'
styles['BodyText'].fontSize=10;styles['BodyText'].leading=15;styles['BodyText'].spaceAfter=9
styles['Title'].fontName='DV-Bold';styles['Title'].fontSize=24;styles['Title'].leading=29;styles['Title'].alignment=TA_LEFT
styles['Heading1'].fontName='DV-Bold';styles['Heading1'].fontSize=19;styles['Heading1'].leading=24;styles['Heading1'].spaceAfter=14
styles['Heading2'].fontName='DV-Bold';styles['Heading2'].fontSize=12;styles['Heading2'].leading=16
styles.add(ParagraphStyle(name='Small',fontName='DV',fontSize=8,leading=11,textColor=colors.HexColor('#536371')))
story=[]
def p(s,style='BodyText'):story.append(Paragraph(s,styles[style]))
def title(k,s):p(f'SQL / PORTFOLIO · {k}','Small');p(s,'Heading1')
def table(rows,widths):
 t=Table([[Paragraph(str(x),styles['Small']) for x in row] for row in rows],colWidths=widths,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7eef2')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor(BLUE)),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#dce3e8'))]));story.append(t);story.append(Spacer(1,10))
def fig(n):story.append(Image(str(FIG/f'{n}.png'),width=495,height=165));story.append(Spacer(1,8))
title('01 / РЕШЕНИЕ','Повторные покупки и возможности роста')
p('Аналитическая записка · учебный интернет-магазин · PostgreSQL','Small')
p('<b>Рекомендация:</b> проверить одно сообщение с дополняющими аксессуарами без скидки на 31-й день после первой покупки. Масштабировать только после подтверждения дополнительной прибыли. Эффект сообщения предстоит измерить в эксперименте.')
fig('monthly')
table([['Метрика','2012','2013'],['Сумма продаж','5 842 231','16 349 836'],['Покупатели','3 255','17 427'],['Заказов на покупателя','1,004','1,221'],['Средний чек','1 787,16','768,07']],[225,135,135])
p('Выручка выросла на <b>10 507 605 (+179,9%)</b>. Последовательное разложение «покупатели → частота → чек» даёт +25 436 589, +6 764 487 и −21 693 471 соответственно. Вклады сходятся с общим изменением до округления. Величины вкладов зависят от порядка замены. Для установления причин изменения покупок потребуется отдельное исследование.')
p('За 1–28 января 2014 сумма продаж составила 45 642 против 781 891 годом ранее. В январе 2014 в выборке отсутствуют Bikes. Чтобы объяснить падение, сначала нужно проверить полноту выгрузки и ассортимент.')
p('Источник всех чисел: originals/*.csv → sql/01–05 → outputs/*.json. Единицы денег и полнота учёта возвратов неизвестны. Период: 2010-12-29–2014-01-28; срез 2014-01-29.','Small')
story.append(PageBreak())
title('02 / ПОВЕДЕНИЕ','Как часто покупатели возвращаются')
p('<b>37,14%</b> клиентов имеют второй заказ за всё доступное наблюдение. У старых клиентов было больше времени. Для 180 дней корректная зрелая база даёт <b>1 342 / 12 503 = 10,73%</b>. Такое ограничение позволяет сравнить клиентов за одинаковый срок.')
fig('repeat')
p('В Mixed входят клиенты с несколькими категориями в первой корзине. В Clothing наблюдается более высокая доля возврата. Для проверки предложения выбрана Accessories, где доступна более крупная база. Реакция каждой категории на кампанию пока неизвестна.')
table([['Метрика','Определение','Результат'],['M1 / M3 / M6','Покупка именно в целевом календарном месяце; одна и та же зрелая база 11 414 клиентов','1,95% / 2,30% / 2,83%'],['Повтор за 180 дней','Второй заказ ≤180 дней, наблюдение ≥180 дней','10,73%'],['Kaplan–Meier к 180 дням','Product-limit с административным цензурированием','11,14%']],[100,300,95])
p('<b>Сравнение за одинаковый период.</b> В одинаковых когортах января–июня 2013 при общих весах месяцев: Accessories 20,48%, Bikes 3,53%, Clothing 25,45%, Mixed 9,90%. Для Bikes здесь лишь 176 клиентов. При одинаковых весах месяцев различия в клиентах и товарах сохраняются.')
p('Первая покупка в данных может не быть первой в жизни. Декабрь 2010 наблюдается только с 29-го числа. Незавершённые месяцы в матрице остаются NULL. Нулевая покупка в M1 не исключает покупку в M6. Оценка Kaplan–Meier предполагает независимость окончания наблюдения от склонности к повтору. Изменения ассортимента и состава клиентов могут нарушать это условие.')
story.append(PageBreak())
title('03 / ЭКОНОМИКА','При каких условиях окупится сообщение')
p('Предложение предназначено для клиентов с первой корзиной только из Accessories, которые к 30-му дню ещё не сделали второй заказ. На 31-й день им отправляют одно сообщение с дополняющими товарами без скидки. Результат оценивают по покупкам в дни 31–120.')
p('Историческая база: 4 329 подходящих клиентов, 443 вторых заказа; конверсия <b>10,23%</b>, средний чек второго заказа <b>53,07</b>. Эти показатели используются как историческая база сравнения. В срезе найдено 416 покупателей Accessories с единственной покупкой 30–60 дней назад. Для контакта с ними потребовались бы актуальные сведения и согласия.')
fig('scenario')
table([['Гипотеза прироста','Прибыль без скидки','Прибыль со скидкой 5%'],['0 п.п.','−250,00','−521,54'],['+1 п.п.','−64,26','−362,33'],['+2 п.п.','+121,49','−203,12'],['+4 п.п.','+492,98','+115,30']],[150,170,175])
p('На 1 000 контактов приняты маржа 35%, цена контакта 0,15 и расходы на настройку 100. Расчёт учитывает один второй заказ на клиента. При приросте конверсии на 2 п.п. дополнительная выручка составит 1 061,40, прибыль без скидки 121,49, ROI затрат 48,6%. Эти значения получены при заданных допущениях. Фактический эффект ещё не измерен.')
p('Формула: N × Δp × A × m − N × c − F − N × (p₀ + Δp) × A × d. Скидку получают и органические покупатели. Порог окупаемости: <b>+1,35 п.п.</b> без скидки, <b>+3,28 п.п.</b> со скидкой 5%. При более низкой марже или меньшем тираже порог растёт.')
story.append(PageBreak())
title('04 / ПРОВЕРКА','Как проверить предложение')
p('На 31-й день подходящих клиентов случайно распределяют между двумя равными группами с учётом месяца входа и диапазона первого чека. Тестовая группа получает сообщение, контрольная продолжает получать обычную коммуникацию. Назначение сохраняют, пересекающиеся кампании исключают. В анализе учитывают всех назначенных клиентов, включая тех, кому сообщение не доставлено.')
p('<b>Основная метрика:</b> доля назначенных клиентов со вторым оплаченным неотменённым заказом в дни 31–120. <b>Критерий решения:</b> дополнительная маржинальная прибыль на назначенного клиента после контактов, настройки, возвратов и скидок. Дополнительно отслеживают жалобы, отписки и возвраты. Допустимые пределы согласуют до старта.')
p('<b>Размер.</b> Для +2 п.п. от базы 10,23%, α=5% (двусторонний тест), мощности 80%: примерно <b>3 913 клиентов на группу</b>. Размер выборки рассчитан для конверсии. Для прибыли нужен отдельный расчёт с учётом разброса значений. 416 текущих кандидатов недостаточно. Потребуются новые участники и 90 дней наблюдения каждого. Календарную длительность без потока клиентов определить нельзя.')
p('<b>Анализ.</b> Заранее зафиксировать основную метрику, окно, выборку и исключения. Проверить дисбаланс групп, назначения и доставку. Анализ проводить в заранее согласованный момент. Рассчитать разность долей с 95% доверительным интервалом и bootstrap-интервал прибыли по клиентам. Расширять кампанию при полезном экономическом эффекте и приемлемом уровне жалоб, отписок и возвратов.')
p('Что может помешать','Heading2')
p('Мы не знаем, способно ли сообщение вызвать дополнительную покупку. Оно может лишь приблизить уже запланированный заказ или раздражать клиента. Скидка дополнительно расходует маржу на органические покупки. Инициатива разумна при актуальных данных, согласованном канале, доступном ассортименте и подтверждённой марже.')
p('Надёжность и границы','Heading2')
p('SQL-проверки и более 20 тысяч независимых сравнений Python с CSV пройдены. Восстановлены 16 дат внутри заказов (4 958 суммы), исключены 3 строки на 34. Проект остаётся учебным; коммерческое внедрение и A/B-тест пока не проводились. Версия подготовлена с помощью ИИ. Для самостоятельной защиты нужно разобраться в расчётах и повторить их.')
p('Данные: github.com/yy4zcbmxhx-hash/SQL_report; непосредственный учебный источник DataWithBaraa/sql-data-analytics-project (MIT, текст лицензии сохранён). Продажи и товары совпадают построчно, данные клиентов совпадают после исключения технического create_date. Полная история происхождения и денежные определения не установлены. Подробности: docs/sources.md, docs/audit.md, docs/interview.md.','Small')
def footer(c,doc):
 c.setFont('DV',8);c.setFillColor(colors.HexColor('#536371'));c.drawString(50,27,'Учебный анализ · исторические данные · эффект кампании не измерен');c.drawRightString(545,27,str(doc.page))
doc=SimpleDocTemplate(str(OUT/'analytical_memo.pdf'),pagesize=(595,842),rightMargin=50,leftMargin=50,topMargin=42,bottomMargin=45,title='Повторные покупки: аналитическая записка',author='SQL portfolio')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT/'analytical_memo.pdf')
