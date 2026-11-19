import React, { useEffect, useRef, useState } from 'react';

type Row = Record<string, string | number | null>;
type ShardPlan = {shard:string;host:string|null;plan:string|null;pipeline:string[];keys_examined:number|null;docs_examined:number|null;matched:number|null;partial_groups:number|null;time_ms:number|null};
type Plan = {topology:'sharded'|'single';merge_type:string|null;shards_part:string[];merger_part:string[];shards:ShardPlan[]};
type Execution = {engine:'aggregate'|'mapreduce';elapsed_ms:number;groups_returned:number;plan:Plan|null};
type Result = {
  metric:Metric;corpus_scope:string;document_type:string|null;engine:string;limit:number|null;matched_documents:number;rows:Row[];
  coverage:{field:string;grouped_documents:number;matched_documents:number;consistent:boolean}|null;
  executions:Execution[];
  comparison:{equal:boolean;rows_compared:number;differences:{row:number|null;field:string;aggregate:unknown;mapreduce:unknown}[]}|null;
  topology:{sharded:boolean;shards:{shard:string;documents:number}[]};
};
type Metric = 'map_pool'|'document_types'|'series_scores'|'top_players';
type Column = {key:string;label:string;format?:(row:Row)=>React.ReactNode;numeric?:boolean};

const fmt = (value:number|null|undefined, digits=1) => value===null||value===undefined?'—':new Intl.NumberFormat('uk-UA',{maximumFractionDigits:digits}).format(value);
const pct = (value:number|null|undefined) => value===null||value===undefined?'—':new Intl.NumberFormat('uk-UA',{style:'percent',maximumFractionDigits:1}).format(value);
const n = (row:Row,key:string) => row[key] as number|null;
const typeName:Record<string,string> = {series:'Підсумки матчів',map:'Окремі карти'};
const engineName:Record<string,string> = {aggregate:'Aggregation pipeline',mapreduce:'mapReduce (JavaScript)'};

const METRICS:Record<Metric,{title:string;help:string;columns:Column[]}> = {
  map_pool:{title:'Пул карт',help:'Лише документи типу «карта»: кількість зіграних карт, середня кількість раундів, середня різниця в рахунку та частка перемог першої команди.',columns:[
    {key:'map_name',label:'Карта',format:r=>r.map_name??<em className="muted">Не вказано в джерелі</em>},
    {key:'maps',label:'Карт',numeric:true,format:r=>fmt(n(r,'maps'))},
    {key:'share',label:'Частка',numeric:true,format:r=>pct(n(r,'share'))},
    {key:'avg_rounds',label:'Сер. раундів',numeric:true,format:r=>fmt(n(r,'avg_rounds'),2)},
    {key:'avg_margin',label:'Сер. різниця',numeric:true,format:r=>fmt(n(r,'avg_margin'),2)},
    {key:'team1_win_share',label:'Перемоги команди 1',numeric:true,format:r=>pct(n(r,'team1_win_share'))}]},
  document_types:{title:'Типи документів',help:'Кількість документів за корпусом і типом. Серії та карти лише рахуються окремими рядками й ніколи не підсумовуються між собою.',columns:[
    {key:'corpus_scope',label:'Корпус'},
    {key:'document_type',label:'Тип',format:r=>typeName[String(r.document_type)]??'—'},
    {key:'documents',label:'Документів',numeric:true,format:r=>fmt(n(r,'documents'))},
    {key:'with_players',label:'Зі статистикою гравців',numeric:true,format:r=>fmt(n(r,'with_players'))},
    {key:'avg_players',label:'Сер. гравців',numeric:true,format:r=>fmt(n(r,'avg_players'),2)},
    {key:'team1_win_share',label:'Перемоги команди 1',numeric:true,format:r=>pct(n(r,'team1_win_share'))}]},
  series_scores:{title:'Рахунки серій',help:'Лише підсумки матчів: розподіл рахунків серій (більший:менший) за форматом BO1/BO3/BO5.',columns:[
    {key:'best_of',label:'Формат',format:r=>r.best_of===null?<em className="muted">Не вказано</em>:'BO'+r.best_of},
    {key:'score',label:'Рахунок',format:r=>r.score??<em className="muted">Без рахунку</em>},
    {key:'documents',label:'Серій',numeric:true,format:r=>fmt(n(r,'documents'))},
    {key:'share',label:'Частка',numeric:true,format:r=>pct(n(r,'share'))},
    {key:'team1_wins',label:'Перемог 1 / 2',numeric:true,format:r=>`${fmt(n(r,'team1_wins'))} / ${fmt(n(r,'team2_wins'))}`}]},
  top_players:{title:'Найкращі гравці',help:'Розгортання масиву гравців ($unwind) і сума показників за player_id. Тип документа обов’язковий: статистика серії вже містить статистику її карт.',columns:[
    {key:'rank',label:'#',numeric:true},
    {key:'name',label:'Гравець',format:r=><>{r.name??'—'}<small className="muted block">ID {r.player_id}</small></>},
    {key:'documents',label:'Документів',numeric:true,format:r=>fmt(n(r,'documents'))},
    {key:'kills',label:'Вбивства',numeric:true,format:r=>fmt(n(r,'kills'))},
    {key:'deaths',label:'Смерті',numeric:true,format:r=>fmt(n(r,'deaths'))},
    {key:'kd',label:'K/D',numeric:true,format:r=>fmt(n(r,'kd'),2)},
    {key:'kills_per_document',label:'Вбивств / док.',numeric:true,format:r=>fmt(n(r,'kills_per_document'),2)},
    {key:'avg_adr',label:'ADR',numeric:true,format:r=>fmt(n(r,'avg_adr'))},
    {key:'avg_kast',label:'KAST, %',numeric:true,format:r=>fmt(n(r,'avg_kast'))}]},
};

async function request(path:string, signal:AbortSignal):Promise<Result> {
  let response:Response;
  try { response = await fetch('/api/v1'+path,{signal}); }
  catch(e) { if((e as Error).name==='AbortError') throw e; throw new Error('Немає зв’язку із сервером. Перевірте підключення та спробуйте ще раз.'); }
  const data = await response.json().catch(()=>null);
  if(!response.ok){
    if(response.status===422) throw new Error('Некоректні параметри запиту: '+(typeof data?.detail==='string'?data.detail:'перевірте показник, корпус і тип документа.'));
    if(response.status===504||response.status===502) throw new Error('Запит виконувався надто довго й був перерваний. Спробуйте рушій Aggregation або вужчий корпус.');
    if(response.status>=500) throw new Error('База документів недоступна або запит перевищив ліміт часу (60 с). Спробуйте ще раз.');
    throw new Error('Не вдалося виконати запит. Спробуйте ще раз.');
  }
  if(!data) throw new Error('Сервер повернув некоректну відповідь.');
  return data;
}

type Form = {metric:Metric;corpus_scope:string;document_type:string;engine:string;limit:number;explain:boolean};
const DEFAULT:Form = {metric:'map_pool',corpus_scope:'all',document_type:'',engine:'both',limit:20,explain:true};
const fixedType:Partial<Record<Metric,string>> = {map_pool:'map',series_scores:'series'};

function toQuery(form:Form) {
  const params = new URLSearchParams({metric:form.metric,corpus_scope:form.corpus_scope,engine:form.engine,explain:String(form.explain)});
  if(form.metric==='top_players') params.set('limit',String(form.limit));
  if(!fixedType[form.metric] && form.document_type) params.set('document_type',form.document_type);
  return params.toString();
}

export function Distributed(){
  const [form,setForm] = useState<Form>(DEFAULT);
  const [applied,setApplied] = useState(()=>toQuery(DEFAULT));
  const [run,setRun] = useState(0);
  const [result,setResult] = useState<Result|null>(null);
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState('');
  const [elapsed,setElapsed] = useState(0);
  const startedAt = useRef(0);

  useEffect(()=>{
    const abort = new AbortController(); setLoading(true); setError(''); startedAt.current = Date.now(); setElapsed(0);
    const tick = setInterval(()=>setElapsed(Date.now()-startedAt.current),200);
    request('/distributed/map-reduce?'+applied,abort.signal).then(setResult)
      .catch(e=>{if(!abort.signal.aborted)setError((e as Error).message);})
      .finally(()=>{clearInterval(tick); if(!abort.signal.aborted)setLoading(false);});
    return ()=>{clearInterval(tick);abort.abort();};
  },[applied,run]);

  const set = <K extends keyof Form>(key:K,value:Form[K]) => setForm(f=>({...f,[key]:value}));
  const playersNeedType = form.metric==='top_players' && !form.document_type;
  const meta = result ? METRICS[result.metric] : null;
  const rows:Row[] = result ? result.rows.map((row,i)=>({...row,rank:i+1})) : [];

  return <section className="panel distributed">
    <div className="panel-title"><h2>Розподілені запити</h2><span className="pill">MAP-REDUCE / 3 ШАРДИ</span></div>
    <p className="hint">Запит надсилається через <code>mongos</code> на кожен шард: шард фільтрує свої документи <code>template_version = "2"</code> і рахує часткові групи (map + combine), після чого один вузол зливає їх у підсумок (reduce).</p>
    <form onSubmit={e=>{e.preventDefault(); if(playersNeedType)return; setApplied(toQuery(form)); setRun(v=>v+1);}}>
      <div className="filters dist-filters">
        <label>Показник<select value={form.metric} onChange={e=>{const metric=e.target.value as Metric; setForm(f=>({...f,metric,document_type:metric==='top_players'?(f.document_type||'map'):fixedType[metric]?'':f.document_type}));}}>
          {(Object.keys(METRICS) as Metric[]).map(key=><option key={key} value={key}>{METRICS[key].title}</option>)}</select></label>
        <label>Корпус<select value={form.corpus_scope} onChange={e=>set('corpus_scope',e.target.value)}>
          <option value="all">Усі (kaggle-cs + synthetic-cs)</option><option value="kaggle-cs">kaggle-cs · реальні матчі</option><option value="synthetic-cs">synthetic-cs · синтетичні</option></select></label>
        <label>Тип документа{fixedType[form.metric]
          ? <select disabled value={fixedType[form.metric]}><option value={fixedType[form.metric]}>{typeName[fixedType[form.metric]!]} (фіксовано)</option></select>
          : <select value={form.document_type} onChange={e=>set('document_type',e.target.value)} aria-invalid={playersNeedType}>
              {form.metric!=='top_players'&&<option value="">Усі типи (окремими рядками)</option>}
              <option value="series">Підсумки матчів</option><option value="map">Окремі карти</option></select>}</label>
        <label>Рушій<select value={form.engine} onChange={e=>set('engine',e.target.value)}>
          <option value="both">Обидва + порівняння</option><option value="aggregate">Aggregation pipeline</option><option value="mapreduce">mapReduce (JavaScript)</option></select></label>
        {form.metric==='top_players'
          ? <label>Топ N<input type="number" min={1} max={100} value={form.limit} onChange={e=>set('limit',Number(e.target.value))}/></label>
          : <label className="check"><span>План виконання</span><span className="check-row"><input type="checkbox" checked={form.explain} onChange={e=>set('explain',e.target.checked)}/> explain по шардах</span></label>}
      </div>
      <div className="filter-help"><p>{METRICS[form.metric].help}</p>
        <button className="primary" type="submit" disabled={loading||playersNeedType||(form.metric==='top_players'&&(!Number.isInteger(form.limit)||form.limit<1||form.limit>100))}>Виконати ↗</button></div>
    </form>

    <div className="results-heading" aria-live="polite">
      <span>{loading?`Виконується на всіх шардах… ${fmt(elapsed/1000)} с`:result?`${fmt(result.matched_documents)} документів → ${fmt(result.rows.length)} груп`:'Немає результату'}</span>
      <small>{loading&&applied.includes('engine=mapreduce')||loading&&applied.includes('engine=both')?'mapReduce виконує JavaScript на кожному шарді — це може тривати до 10 с':'Через mongos · scatter-gather'}</small>
    </div>

    {error&&<div className="error" role="alert">{error} <button onClick={()=>setRun(v=>v+1)}>Повторити запит</button></div>}
    {loading&&!result&&<div className="dist-loading" aria-busy="true"><span className="spinner" aria-hidden="true"/>Шарди обчислюють часткові агрегати…</div>}

    {result&&!error&&<div className={loading?'dist-result stale':'dist-result'} aria-busy={loading}>
      <Topology result={result}/>
      <Checks result={result}/>
      {result.rows.length===0
        ? <div className="empty"><span>∅</span><h3>Немає документів для агрегації</h3><p>Для обраного корпусу й типу немає документів <code>template_version = "2"</code>. Оберіть інший корпус або імпортуйте набір на сторінці імпорту.</p></div>
        : <><h3 className="dist-h">{meta!.title} · {result.document_type?typeName[result.document_type]:'усі типи'} · {result.corpus_scope==='all'?'обидва корпуси':result.corpus_scope}</h3>
          <div className="table-wrap"><table className="data-table"><thead><tr>{meta!.columns.map(c=><th key={c.key} className={c.numeric?'num':''}>{c.label}</th>)}</tr></thead>
            <tbody>{rows.map((row,i)=><tr key={i}>{meta!.columns.map(c=><td key={c.key} className={c.numeric?'num':''}>{c.format?c.format(row):String(row[c.key]??'—')}</td>)}</tr>)}</tbody></table></div></>}
      {result.executions.map(execution=><ExecutionView key={execution.engine} execution={execution}/>)}
    </div>}
  </section>;
}

function Topology({result}:{result:Result}){
  const total = result.topology.shards.reduce((sum,s)=>sum+s.documents,0);
  return <div className="shard-grid" aria-label="Розподіл колекції по шардах">
    {result.topology.shards.map(shard=><div key={shard.shard} className="shard-card">
      <span>{result.topology.sharded?'ШАРД':'БЕЗ ШАРДУВАННЯ'}</span><strong>{shard.shard}</strong>
      <small>{fmt(shard.documents)} док. у колекції · {pct(total?shard.documents/total:0)}</small>
      <div className="bar"><i style={{width:`${total?100*shard.documents/total:0}%`}}/></div></div>)}
  </div>;
}

function Checks({result}:{result:Result}){
  const c = result.comparison, cov = result.coverage;
  return <div className="checks">
    {result.executions.map(e=><div key={e.engine} className="check-card"><span>{engineName[e.engine]}</span><strong>{fmt(e.elapsed_ms,0)} мс</strong><small>{fmt(e.groups_returned)} груп повернуто застосунку</small></div>)}
    {cov&&<div className={'check-card '+(cov.consistent?'ok':'bad')}><span>ПОВНОТА</span><strong>{cov.consistent?'✓ Сходиться':'✗ Розбіжність'}</strong><small>Σ груп = {fmt(cov.grouped_documents)} із {fmt(cov.matched_documents)} документів</small></div>}
    {c&&<div className={'check-card '+(c.equal?'ok':'bad')}><span>AGGREGATE ⇄ MAPREDUCE</span><strong>{c.equal?'✓ Збігаються':'✗ Відрізняються'}</strong><small>{c.equal?`${fmt(c.rows_compared)} рядків, усі поля`:c.differences.slice(0,2).map(d=>`рядок ${d.row??'—'}, ${d.field}`).join('; ')}</small></div>}
  </div>;
}

function ExecutionView({execution}:{execution:Execution}){
  const plan = execution.plan;
  return <details className="execution" open={execution.engine==='aggregate'}>
    <summary>{engineName[execution.engine]} · {fmt(execution.elapsed_ms,0)} мс{plan?` · злиття: ${plan.merge_type==='mongos'?'на mongos':plan.merge_type==='anyShard'?'на одному з шардів':plan.merge_type==='primaryShard'?'на первинному шарді':plan.merge_type??'локально'}`:''}</summary>
    {!plan?<p className="hint">План виконання вимкнено. Увімкніть «explain по шардах», щоб побачити розбиття на map- і reduce-частини.</p>:<>
      <div className="phases">
        <div><span className="eyebrow">MAP + COMBINE · НА КОЖНОМУ ШАРДІ</span><div className="chips">{(plan.shards_part.length?plan.shards_part:plan.shards[0]?.pipeline??[]).map((s,i)=><code key={i}>{s}</code>)}</div></div>
        <div><span className="eyebrow">REDUCE · ЗЛИТТЯ</span><div className="chips">{plan.merger_part.length?plan.merger_part.map((s,i)=><code key={i}>{s}</code>):<em className="muted">Одна база без шардування — злиття не потрібне</em>}</div></div>
      </div>
      <div className="table-wrap"><table className="data-table compact"><thead><tr><th>Шард</th><th>План на шарді</th><th className="num">Ключів</th><th className="num">Документів</th><th className="num">Відібрано</th><th className="num">Часткових груп</th><th className="num">Час, мс</th></tr></thead>
        <tbody>{plan.shards.map(s=><tr key={s.shard}><td><strong>{s.shard}</strong><small className="muted block">{s.host??''}</small></td><td className="plan">{s.plan??'—'}</td>
          <td className="num">{fmt(s.keys_examined)}</td><td className="num">{fmt(s.docs_examined)}</td><td className="num">{fmt(s.matched)}</td><td className="num">{fmt(s.partial_groups)}</td><td className="num">{fmt(s.time_ms)}</td></tr>)}</tbody>
        <tfoot><tr><td colSpan={4}>Разом по шардах</td><td className="num">{fmt(plan.shards.reduce((a,s)=>a+(s.matched??0),0))}</td><td className="num">{fmt(plan.shards.reduce((a,s)=>a+(s.partial_groups??0),0))}</td><td className="num">max {fmt(Math.max(0,...plan.shards.map(s=>s.time_ms??0)))}</td></tr></tfoot></table></div>
      <p className="hint">«Часткових груп» — скільки проміжних записів шард передав на злиття. Час шарду виміряно під час повторного виконання для explain.</p>
    </>}
  </details>;
}
