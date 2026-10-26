import React from 'react';
import {EvidenceChart,DataComponent,DataTable,Section,Filters,useDataApp,useDashboardTabs,useSectionFilters} from '../../data-app-public.jsx';

const cols = (pairs) => pairs.map(([field,label])=>({field,label,renderCell:v=>v==null?'—':typeof v==='number'?v.toLocaleString('ru-RU',{maximumFractionDigits:2}):v}));
function Table({id,q,title,rows,columns}) {return <DataComponent id={id} queryId={q} title={title} kind="table" variant="card" displayRows={rows} sourceRows={rows}><DataTable rows={rows} columns={cols(columns)} searchable={false}/></DataComponent>}
export function DashboardContent(){
 const {queries}=useDataApp();const rows=q=>queries[q].rows;
 const {activeTabId}=useDashboardTabs([{id:'sales',label:'Выручка'},{id:'retention',label:'Повторные покупки'},{id:'initiative',label:'Гипотеза и экономика'}]);
 const scope=useSectionFilters([{id:'days',label:'Горизонт, дней',field:'days',defaultValue:'180',queryIds:['repeat_horizons']}],{},{id:'repeat-horizon'});
 const rp=scope.componentProps('repeat_horizons',['first_category','days']);
 const repeat=rp.displayRows.map(r=>({...r,repeatRate:r.repeat_rate,horizon:r.days+' дней'}));
 const full=rows('monthly').filter(r=>r.full_month);
 const newReturning=rows('monthly_segments').filter(r=>r.month>='2011-01-01'&&r.month<'2014-01-01');
 const bridge=rows('revenue_bridge')[0];
 const contributions=[{factor:'Покупатели',change:bridge.buyers_effect},{factor:'Частота',change:bridge.frequency_effect},{factor:'Средний чек',change:bridge.aov_effect}];
 const cohorts=rows('cohort_retention').filter(r=>[1,3,6].includes(r.month_age)).map(r=>({...r,age:'M'+r.month_age,cohort:r.cohort.slice(0,7),purchaseRetention:r.retention}));
 return <div>
 <p>Учебный датасет · покупки 29.12.2010–28.01.2014 · суммы в единицах источника · дата анализа 29.01.2014.</p>
 {(!activeTabId||activeTabId==='sales')&&<>
 <Section id="sales-period" title="Полные месяцы с января 2011 по декабрь 2013">
 <EvidenceChart id="monthly-revenue" queryId="monthly_segments" title="Продажи новым и повторным клиентам" variant="card" rows={newReturning} sourceRows={newReturning} height={320} spec={{type:'bar',x:'month',y:'revenue',series:'segment',yLabel:'Сумма продаж',legend:{labels:{New:'Новые',Returning:'Повторные'}}}}/>
 </Section>
 <Section id="drivers-heading" title="Факторы выручки" columns={2}>
 <EvidenceChart id="buyers" queryId="monthly" title="Покупатели по месяцам" variant="card" rows={full} sourceRows={full} height={260} spec={{type:'line',x:'month',y:'buyers'}}/>
 <EvidenceChart id="aov" queryId="monthly" title="Средний чек по месяцам" variant="card" rows={full} sourceRows={full} height={260} spec={{type:'line',x:'month',y:'aov',valueDecimals:1}}/>
 <EvidenceChart id="frequency" queryId="monthly" title="Заказов на покупателя в месяц" variant="card" rows={full} sourceRows={full} height={260} spec={{type:'line',x:'month',y:'frequency',valueDecimals:3}}/>
 </Section>
 <Section id="bridge-heading" title="Декомпозиция за полные годы">
 <EvidenceChart id="bridge" queryId="revenue_bridge" title="Изменение выручки: 2012 → 2013" variant="card" rows={contributions} sourceRows={[bridge]} height={260} dataInputs={{beginning:bridge.revenue_before,ending:bridge.revenue_after}} spec={{type:'waterfall',x:'factor',y:'change',valueDecimals:0}}/>
 </Section>
 <Section id="january-heading" title="1–28 января: одинаковые окна наблюдения">
 <EvidenceChart id="january-category" queryId="january_category" title="Продажи по категориям" variant="card" rows={rows('january_category').map(r=>({...r,year:String(r.year)}))} sourceRows={rows('january_category')} height={270} spec={{type:'bar',x:'category',y:'revenue',series:'year'}}/>
 <p>В январе 2014 нет наблюдаемых продаж Bikes. Без проверки полноты выгрузки и ассортимента падение нельзя трактовать как эффект удержания.</p>
 </Section></>}
 {activeTabId==='retention'&&<>
 <Section id="cohort-heading" title="Возврат именно в M1, M3 и M6">
 <p>Клиенты объединены по месяцу первой наблюдаемой покупки. Пропуск обозначает месяц, который ещё нельзя наблюдать полностью. История покупок до начала датасета неизвестна.</p>
 <EvidenceChart id="cohort-heatmap" queryId="cohort_retention" title="Покупательский retention по когортам" variant="card" rows={cohorts} sourceRows={rows('cohort_retention').filter(r=>[1,3,6].includes(r.month_age))} height={920} spec={{type:'heatmap',x:'age',y:'purchaseRetention',series:'cohort',colorDomain:[0,1],missingValues:'gap',showValues:true}}/>
 <Table id="cohort-profile" q="cohort_summary" title="Одинаковые 31 зрелая когорта, 11 414 покупателей" rows={rows('cohort_summary').map(r=>({...r,retention_percent:100*r.retention}))} columns={[["month_age","Месяц"],["eligible","Клиенты"],["active","Вернулись"],["retention_percent","Возврат, %"]]}/>
 </Section>
 <Section id="repeat-heading" title="Второй заказ за фиксированный срок" filters={<Filters {...scope.filterProps}/> }>
 <EvidenceChart id="repeat-category" queryId="repeat_horizons" title="Доля второго заказа по категории первой корзины" variant="card" {...rp} rows={repeat} height={300} spec={{type:'bar',x:'first_category',y:'repeatRate',series:'horizon',stackable:false,valueDecimals:1}}/>
 <Table id="repeat-denominators" q="repeat_horizons" title="Размер сравниваемых групп" rows={repeat} columns={[["first_category","Первая категория"],["days","Дней"],["eligible","Достаточно наблюдения"],["repeated","Второй заказ"]]}/>
 </Section>
 <Section id="standard-heading" title="Проверка различий между категориями">
 <EvidenceChart id="standardized" queryId="category_standardized" title="180 дней: общие веса когорт января–июня 2013" variant="card" rows={rows('category_standardized').map(r=>({...r,repeatRate:r.standardized_rate}))} sourceRows={rows('category_standardized')} height={280} spec={{type:'bar',x:'first_category',y:'repeatRate',stackable:false}}/>
 <EvidenceChart id="km" queryId="km_second_order" title="Второй заказ с учётом правого цензурирования" variant="card" rows={rows('km_second_order').filter(r=>r.day<=365).map(r=>({...r,repeatRate:r.cumulative_repeat}))} sourceRows={rows('km_second_order').filter(r=>r.day<=365)} height={280} spec={{type:'line',x:'day',y:'repeatRate',xLabel:'Дней после первой покупки',stackable:false}}/>
 <p>Оценка Kaplan–Meier учитывает разную продолжительность наблюдения клиентов. Изменения ассортимента и состава покупателей ограничивают её переносимость. Различия между категориями требуют отдельного исследования причин.</p>
 </Section></>}
 {activeTabId==='initiative'&&<>
 <Section id="initiative-heading" title="Проверить напоминание о дополняющих аксессуарах">
 <p>Предложение предназначено для клиентов с первой корзиной только из Accessories, которые к 30-му дню ещё не сделали второй заказ. На 31-й день тестовая группа получает одно сообщение с дополняющими товарами без скидки. Контрольная группа получает обычную коммуникацию. Сравниваются покупки в дни 31–120.</p>
 <Table id="baseline" q="campaign_baseline" title="Историческая база подходящего сегмента" rows={rows('campaign_baseline').filter(r=>r.first_category==='Accessories').map(r=>({...r,baseline_percent:100*r.baseline_rate}))} columns={[["eligible","Клиенты"],["repeat_31_120","Вернулись"],["baseline_percent","База, %"],["second_order_aov","Чек второго заказа"]]}/>
 </Section>
 <Section id="scenario-heading" title="Расчёт сценариев на 1 000 контактов">
 <EvidenceChart id="scenario" queryId="scenarios" title="Дополнительная прибыль: без скидки и со скидкой 5%" variant="card" rows={rows('scenarios').map(r=>({...r,offer:r.discount===0?'Без скидки':'Скидка 5%'}))} sourceRows={rows('scenarios')} height={320} spec={{type:'bar',x:'uplift_pp',y:'incremental_profit',series:'offer',xLabel:'Прирост конверсии, п.п.',yLabel:'Дополнительная прибыль'}}/>
 <p>Допущения: маржа 35%, контакт 0,15, настройка 100, средний чек 53,07. Скидку получают и органические покупатели. Без скидки порог окупаемости +1,35 п.п.; со скидкой 5% составляет +3,28 п.п.</p>
 <p>При базовой конверсии 10,23% для эффекта +2 п.п. нужно примерно 3 913 клиентов на группу (α=5%, мощность 80%). В историческом срезе лишь 416 кандидатов с одной покупкой 30–60 дней назад: для полноценного теста потребуется набор новых когорт. Контактов и согласий на рассылку в данных нет.</p>
 </Section></>}
 </div>
}
