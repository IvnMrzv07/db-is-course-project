import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import {DocumentView, type Doc} from './DocumentView';

type Job = {id:string;status:string;total:number;attempted:number;inserted:number;duplicates:number;rejected:number;validation_rejected:number;backlog:number;target_rate:number;error?:string;updated_at:string};
type Stats = {stored_documents:number;durable_documents_per_second:number;sampled_at:string};
const number = (value:number) => new Intl.NumberFormat('uk-UA',{maximumFractionDigits:1}).format(value);
const statusName:Record<string,string> = {running:'Виконується',paused:'Призупинено',completed:'Завершено',failed:'Помилка'};
async function api(path:string, options:RequestInit = {}) {
  let response:Response;
  try { response = await fetch('/api/v1'+path, options); } catch(e) { if((e as Error).name==='AbortError')throw e; throw new Error('Немає зв’язку із сервером. Перевірте підключення та спробуйте ще раз.'); }
  const data = await response.json().catch(() => ({detail:'Сервер повернув некоректну відповідь'}));
  if (!response.ok) {
    const messages:Record<number,string>={401:'Невірний токен. Натисніть «Вийти» та введіть токен з локального налаштування.',404:'Запис не знайдено. Оновіть список і спробуйте ще раз.',409:'Стан завдання вже змінився. Оновіть дані та повторіть дію.',422:'Перевірте значення полів, діапазон дат і темп від 10 до 5000 цілих документів/с.'};
    throw new Error(response.status>=500?'Сервіс тимчасово недоступний. Спробуйте ще раз після відновлення зв’язку.':messages[response.status]||'Не вдалося виконати запит. Спробуйте ще раз.');
  }
  return data;
}

function App() {
  const [view,setView] = useState<'corpus'|'imports'>('corpus');
  const [stats,setStats] = useState<Stats|null>(null);
  const [statsError,setStatsError] = useState('');
  useEffect(() => {
    let stopped=false; let timer:ReturnType<typeof setTimeout>; const abort=new AbortController();
    const poll=async()=>{ try {const value=await api('/corpus/statistics',{signal:abort.signal}); if(!stopped){setStats(value);setStatsError('');}}
      catch(e){if(!stopped)setStatsError((e as Error).message);} finally {if(!stopped)timer=setTimeout(poll,1000);} };
    void poll(); return ()=>{stopped=true;clearTimeout(timer);abort.abort();};
  },[]);
  return <div className="shell">
    <aside><a className="brand" href="#" onClick={e=>{e.preventDefault();setView('corpus');}}><span className="brand-mark">CS</span><span>ARCHIVE<small>COUNTER-STRIKE DATA</small></span></a>
      <div className="nav-label">РОБОЧИЙ ПРОСТІР</div><nav aria-label="Основна навігація">
      <button className={view==='corpus'?'active':''} onClick={()=>setView('corpus')}><span>▦</span> Корпус документів</button>
      <button className={view==='imports'?'active':''} onClick={()=>setView('imports')}><span>↳</span> Імпорт та моніторинг</button></nav>
      <div className="side-note"><span className="dot"/> Локальний архів<p>Історія матчів.<br/>Дані з перевіреним походженням.</p><small>КУРСОВИЙ ПРОЄКТ · ЕТАПИ 9–12</small></div>
    </aside>
    <main><header><span>РОБОЧИЙ ПРОСТІР / {view==='corpus'?'КОРПУС':'ІМПОРТ'}</span><span className="tag">CS / DATA EXPLORER</span></header>
      <section className="intro"><div className="eyebrow">COUNTER-STRIKE / MATCH RECORDS</div><h1>{view==='corpus'?'Кожен матч має історію.':'Від джерела до архіву.'}</h1><p>{view==='corpus'?'Досліджуйте матчі та карти. Знаходьте факти, команди й результати в одному місці.':'Керуйте завантаженням корпусу та стежте за фактично збереженими даними.'}</p></section>
      <section className="metrics" aria-label="Статистика корпусу"><div><span>ДОКУМЕНТІВ У БАЗІ</span><strong>{stats?number(stats.stored_documents):'—'}</strong><small>Підтверджені записи</small></div><div><span>ШВИДКІСТЬ ЗАПИСУ</span><strong>{stats?number(stats.durable_documents_per_second):'—'} <em>док/с</em></strong><small>Середнє за останні 10 секунд</small></div><div><span>ОСТАННЄ ОНОВЛЕННЯ</span><strong className="clock">{stats?new Date(stats.sampled_at).toLocaleTimeString('uk-UA'):'—'}</strong><small>{statsError?'Зв’язок перервано · дані можуть бути застарілими':'Автоматичне оновлення щосекунди'}</small></div></section>
      {statsError&&<div role="alert" className="error">Статистика недоступна: {statsError}</div>}
      {view==='corpus'?<Corpus/>:<Imports/>}
      <footer><span>CS ARCHIVE</span><span>Фактологічні описи сформовано з локального датасету Kaggle.</span></footer>
    </main></div>;
}
function Corpus(){
  const [filters,setFilters]=useState({q:'',document_type:'',team:'',tournament:'',date_from:'',date_to:''});
  const [applied,setApplied]=useState(''); const [page,setPage]=useState(1); const [refresh,setRefresh]=useState(0);
  const [data,setData]=useState<{items:Doc[];total:number}>({items:[],total:0});
  const [loading,setLoading]=useState(true); const [error,setError]=useState('');
  const [selected,setSelected]=useState<Doc|null>(null); const [opening,setOpening]=useState(false);
  const requestId=useRef(0); const dialog=useRef<HTMLDialogElement>(null); const opener=useRef<HTMLElement|null>(null);
  function close(){dialog.current?.close();setSelected(null);opener.current?.focus();}
  useEffect(()=>{const abort=new AbortController();setLoading(true);setError('');
    api('/documents?'+applied+'&page='+page,{signal:abort.signal}).then(setData).catch(e=>{if(!abort.signal.aborted)setError(e.message);}).finally(()=>{if(!abort.signal.aborted)setLoading(false);});
    return()=>abort.abort();},[applied,page,refresh]);
  useEffect(()=>{if(selected)dialog.current?.showModal();},[selected]);
  useEffect(()=>()=>{requestId.current++;},[]);
  const field=(key:keyof typeof filters)=>({value:filters[key],onChange:(e:React.ChangeEvent<HTMLInputElement|HTMLSelectElement>)=>setFilters({...filters,[key]:e.target.value})});
  async function open(id:string){opener.current=document.activeElement as HTMLElement;const current=++requestId.current;setOpening(true);setError('');try{const doc=await api('/documents/'+id);if(current===requestId.current)setSelected(doc);}catch(e){if(current===requestId.current)setError((e as Error).message);}finally{if(current===requestId.current)setOpening(false);}}
  return <section className="panel"><div className="panel-title"><h2>Дослідити корпус</h2><span className="pill">МАТЧІ / КАРТИ</span></div>
    <form onSubmit={e=>{e.preventDefault();setPage(1);setApplied(new URLSearchParams(Object.entries(filters).filter(([,value])=>value)).toString());setRefresh(value=>value+1);}}>
      <div className="search-row"><label className="search"><span aria-hidden="true">⌕</span><input {...field('q')} maxLength={200} aria-label="Пошук у тексті" placeholder="Пошук у заголовках і текстах…"/></label><button className="primary" type="submit">Знайти <span>↗</span></button></div>
      <div className="filters"><label>Тип документа<select {...field('document_type')}><option value="">Усі документи</option><option value="series">Підсумки матчів</option><option value="map">Окремі карти</option></select></label><label>Команда<input {...field('team')} placeholder="Точна назва" maxLength={200}/></label><label>Турнір<input {...field('tournament')} placeholder="Точна назва" maxLength={200}/></label><label>Від<input type="date" {...field('date_from')}/></label><label>До<input type="date" {...field('date_to')} min={filters.date_from}/></label></div>
      <div className="filter-help"><p>Команда й турнір — точні назви. Якщо не пам’ятаєте назву, скористайтеся пошуком у тексті.</p><button type="button" onClick={()=>{setFilters({q:'',document_type:'',team:'',tournament:'',date_from:'',date_to:''});setApplied('');setPage(1);setRefresh(v=>v+1);}}>Скинути фільтри</button></div>
    </form>
    <div className="results-heading" aria-live="polite"><span>{loading?'Завантаження…':`${number(data.total)} документів`}</span><small>Пошук буквального фрагмента · без ранжування</small></div>
    {error&&<div className="error" role="alert">{error} <button onClick={()=>setRefresh(v=>v+1)}>Повторити запит</button></div>}
    {!loading&&!error&&data.items.length===0&&<div className="empty"><span>⌕</span><h3>Документів не знайдено</h3><p>Змініть фільтри або завантажте корпус на сторінці імпорту.</p></div>}
    <div className="documents" aria-busy={loading}>{!error&&data.items.map(doc=><button className="document" key={doc.id} onClick={()=>void open(doc.id)} disabled={loading||opening}>
      <span className={'doc-icon '+doc.metadata.document_type}>{doc.metadata.document_type==='series'?'M':'К'}</span><div><div className="doc-meta">{doc.metadata.document_type==='series'?'ПІДСУМОК МАТЧУ':'РЕЗУЛЬТАТ КАРТИ'} <span>·</span> {doc.metadata.played_at?.slice(0,10)}</div><h3>{doc.title}</h3><p>{doc.metadata.team1} <span>vs</span> {doc.metadata.team2}</p></div><span className="arrow">↗</span></button>)}</div>
    <div className="pagination"><span>Сторінка {page} із {Math.max(1,Math.ceil(data.total/20))}</span><div><button disabled={page===1||loading} onClick={()=>setPage(page-1)}>← Назад</button><button disabled={page*20>=data.total||loading} onClick={()=>setPage(page+1)}>Далі →</button></div></div>
    <dialog ref={dialog} aria-labelledby="document-title" onCancel={e=>{e.preventDefault();close();}} onClose={()=>{setSelected(null);opener.current?.focus();}}>{selected&&<DocumentView doc={selected} close={close}/>}</dialog>
  </section>;
}
function Imports(){
  const [token,setToken]=useState('');const [draft,setDraft]=useState('');
  const [jobs,setJobs]=useState<Job[]>([]);const [snapshots,setSnapshots]=useState<{id:string;documents:number;validation_rejected:number}[]>([]);
  const [snapshot,setSnapshot]=useState('kaggle-cs');const [rate,setRate]=useState(100);const [rates,setRates]=useState<Record<string,number>>({});
  const [error,setError]=useState('');const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');
  const [page,setPage]=useState(1);const [total,setTotal]=useState(0);const [listLoading,setListLoading]=useState(false);
  const startKey=useRef<string|null>(null);
  const headers=()=>({'Authorization':'Bearer '+token,'Content-Type':'application/json'});
  useEffect(()=>{if(!token)return;setListLoading(true);let stopped=false;let timer:ReturnType<typeof setTimeout>;const abort=new AbortController();
    const poll=async()=>{try{const [list,sources]=await Promise.all([api('/replays?page='+page,{headers:{Authorization:'Bearer '+token},signal:abort.signal}),api('/snapshots',{headers:{Authorization:'Bearer '+token},signal:abort.signal})]);if(!stopped){setJobs(list.items);setTotal(list.total);setSnapshots(sources);setError('');setListLoading(false);}}
      catch(e){if(!stopped){setError((e as Error).message);setListLoading(false);}}finally{if(!stopped)timer=setTimeout(poll,1000);}};
    void poll();return()=>{stopped=true;clearTimeout(timer);abort.abort();};},[token,page]);
  async function action(path:string,method='POST',body?:object){setBusy(true);setNotice('');try{await api(path,{method,headers:headers(),body:body?JSON.stringify(body):undefined});setNotice('Зміни збережено. Показники оновляться автоматично.');}catch(e){setNotice('Помилка: '+(e as Error).message);}finally{setBusy(false);}}
  async function start(){setBusy(true);setNotice('');startKey.current??=crypto.randomUUID();try{await api('/replays',{method:'POST',headers:{...headers(),'Idempotency-Key':startKey.current},body:JSON.stringify({snapshot_id:snapshot,target_rate:rate})});startKey.current=null;setPage(1);setNotice('Завдання створено.');}catch(e){setNotice('Помилка запуску: '+(e as Error).message);}finally{setBusy(false);}}
  return <section className="panel"><div className="panel-title"><h2>Керування імпортом</h2><span className="pill">ОПЕРАТОР</span></div>
    {!token?<form className="auth" onSubmit={e=>{e.preventDefault();setToken(draft);setDraft('');}}><h3>Доступ оператора</h3><p>Введіть токен зі свого локального налаштування. Він зберігається лише в пам’яті цієї сторінки.</p><label>Токен<input type="password" required minLength={24} value={draft} onChange={e=>setDraft(e.target.value)} autoComplete="off"/></label><button className="primary">Підключитися →</button></form>:<>
      <div className="import-form"><label>Підготовлений набір<select value={snapshot} onChange={e=>{setSnapshot(e.target.value);startKey.current=null;}}>{snapshots.map(s=><option key={s.id} value={s.id}>{s.id} · {number(s.documents)} документів</option>)}</select></label><label>Цільовий темп, док/с<input type="number" min={10} max={5000} value={rate} onChange={e=>{setRate(Number(e.target.value));startKey.current=null;}}/></label><button className="primary" disabled={busy||!snapshots.length||!Number.isInteger(rate)||rate<10||rate>5000} onClick={()=>void start()}>Почати імпорт ↗</button><button onClick={()=>{setToken('');setJobs([]);setSnapshots([]);setError('');setNotice('');setPage(1);setTotal(0);}}>Вийти</button></div>
      <p className="hint">Повторний запуск перевіряє той самий корпус без створення дублікатів. Пауза не скасовує вже відправлені пакети.</p>
      {error&&<div className="error" role="alert">{error}</div>}{notice&&<div className="notice" role="status">{notice}</div>}
      {!jobs.length&&!error&&<div className="empty"><h3>Архів починається з першого імпорту</h3><p>Оберіть набір і запустіть завантаження.</p></div>}
      {jobs.map(job=><article className="job" key={job.id}><div className="job-header"><div><span className="eyebrow">ЗАВДАННЯ {job.id.slice(0,8)}</span><h3>{number(job.inserted+job.duplicates+job.rejected)} / {number(job.total)} документів</h3></div><span className={'status '+job.status}>{statusName[job.status]}</span></div><progress aria-label={'Прогрес завдання '+job.id.slice(0,8)} max={Math.max(1,job.total)} value={job.inserted+job.duplicates+job.rejected}/>
        <div className="job-stats">{[['Спроби',job.attempted],['Нові записи',job.inserted],['Дублікати',job.duplicates],['Відхилено',job.rejected],['Відхилено CSV',job.validation_rejected],['У черзі / обробці',job.backlog]].map(([name,value])=><div key={name}><span>{name}</span><strong>{number(Number(value))}</strong></div>)}</div>
        {job.error&&<p className="error">{job.error} Повторіть імпорт новим завданням після усунення причини.</p>}
        {(job.status==='running'||job.status==='paused')&&<div className="job-controls"><label>Темп, док/с<input type="number" min={10} max={5000} value={rates[job.id]??job.target_rate} onChange={e=>setRates({...rates,[job.id]:Number(e.target.value)})}/></label><button disabled={busy||!Number.isInteger(rates[job.id]??job.target_rate)||(rates[job.id]??job.target_rate)<10||(rates[job.id]??job.target_rate)>5000} onClick={()=>void action('/replays/'+job.id+'/rate','PATCH',{target_rate:rates[job.id]??job.target_rate})}>Застосувати</button><button disabled={busy} onClick={()=>void action('/replays/'+job.id+'/'+(job.status==='running'?'pause':'resume'))}>{job.status==='running'?'Ⅱ Призупинити':'▶ Продовжити'}</button></div>}
      </article>)}
      {total>0&&<nav className="pagination" aria-label="Сторінки історії імпорту"><span>Сторінка {page} із {Math.max(1,Math.ceil(total/20))} · {number(total)} завдань</span><div><button disabled={page===1||listLoading} onClick={()=>setPage(p=>p-1)}>← Назад</button><button disabled={page*20>=total||listLoading} onClick={()=>setPage(p=>p+1)}>Далі →</button></div></nav>}
    </>}
  </section>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
