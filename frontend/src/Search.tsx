import React, { useEffect, useRef, useState } from 'react';
import { DocumentView, type Doc } from './DocumentView';

type Bucket = {value:string; count:number};
type Hit = {id:string; score:number|null; title:string; snippet:string; highlights:Record<string,string[]>;
  corpus_scope:string; is_synthetic:boolean; document_type:'series'|'map'; map_name:string|null;
  team1:string|null; team2:string|null; tournament:string|null; played_at:string|null};
type Result = {status:'found'|'empty'; degraded:boolean; total:number; total_relation:string; max_score:number|null;
  hits:Hit[]; took_ms:number|null; elapsed_ms:number; facets:Record<string,Bucket[]>; page:number; page_size:number};
type IndexStatus = {status:string; documents:number; by_corpus_scope:Record<string,number>; cluster:{health:string}};
type Fallback = {items:Doc[]; total:number};
type Filters = {q:string; mode:string; corpus_scope:string; document_type:string; map_name:string; include_synthetic:boolean};
type State =
  | {kind:'loading'}
  | {kind:'result'; result:Result}
  | {kind:'degraded'; reason:string; fallback:Fallback|null; fallbackError:string}
  | {kind:'error'; message:string};

const PAGE_SIZE = 20;
const EMPTY:Filters = {q:'', mode:'all', corpus_scope:'all', document_type:'', map_name:'', include_synthetic:true};
const MODES:Record<string,string> = {all:'Усі слова', any:'Будь-яке слово', phrase:'Точна фраза', fuzzy:'З урахуванням опечаток'};
const MODE_HELP:Record<string,string> = {
  all:'Кожне слово має знайтися хоча б в одному полі: команда, карта, гравець, турнір чи текст.',
  any:'Достатньо одного слова; документи з більшою кількістю збігів вищі за релевантністю.',
  phrase:'Слова мають стояти поруч і в тому самому порядку.',
  fuzzy:'Кожне слово в назвах команд, карт, турнірів і гравців з допуском помилки: 1 для слів 5–8 літер, 2 — від 9 («mirrage», «inferrno»).'};
const FIELD:Record<string,string> = {title:'Заголовок', team1:'Команда 1', team2:'Команда 2', tournament:'Турнір',
  map_name:'Карта', player_names:'Гравці', text:'Текст'};
const SCOPE:Record<string,string> = {'kaggle-cs':'Kaggle (реальні)', 'synthetic-cs':'Синтетичні'};
const fmt = (value:number, digits=0) => new Intl.NumberFormat('uk-UA',{maximumFractionDigits:digits}).format(value);

/** Elasticsearch fragments use \uE000…\uE001 around matches: rendered as <mark>, never as HTML. */
export function Highlighted({text}:{text:string}) {
  let marked = false;
  return <>{text.split(/([\uE000\uE001])/).map((part,i)=>{
    if(part==='\uE000'){marked=true;return null;}
    if(part==='\uE001'){marked=false;return null;}
    return part?(marked?<mark key={i}>{part}</mark>:<React.Fragment key={i}>{part}</React.Fragment>):null;
  })}</>;
}

class HttpError extends Error { constructor(public status:number, message:string, public reason=''){ super(message); } }

async function getJson(path:string, signal:AbortSignal) {
  let response:Response;
  try { response = await fetch('/api/v1'+path,{signal}); }
  catch(e) { if((e as Error).name==='AbortError') throw e; throw new HttpError(0,'Немає зв’язку із сервером.'); }
  const data = await response.json().catch(()=>null);
  if(!response.ok) throw new HttpError(response.status, typeof data?.detail==='string'?data.detail:'HTTP '+response.status, data?.reason??'');
  return data;
}

function params(filters:Filters, page:number) {
  const query = new URLSearchParams({q:filters.q, mode:filters.mode, corpus_scope:filters.corpus_scope,
    include_synthetic:String(filters.include_synthetic), page:String(page), page_size:String(PAGE_SIZE)});
  if(filters.document_type) query.set('document_type',filters.document_type);
  if(filters.map_name) query.set('map_name',filters.map_name);
  return query.toString();
}

/** Degraded mode: the literal (regex, unranked) MongoDB search of the Content service, one corpus at a time. */
const fallbackScope = (filters:Filters) => filters.corpus_scope==='synthetic-cs'?'synthetic-cs':'kaggle-cs';
function fallbackParams(filters:Filters, page:number) {
  const query = new URLSearchParams({q:filters.q.trim(), corpus_scope:fallbackScope(filters), page:String(page)});
  if(filters.document_type) query.set('document_type',filters.document_type);
  return query.toString();
}

/** Shareable state: #search?q=…&mode=…&corpus_scope=…&document_type=…&map_name=…&include_synthetic=false */
function fromLocation():Filters {
  const query = new URLSearchParams(location.hash.split('?')[1]??'');
  const pick = (key:keyof Filters, allowed?:string[]) => {const v=query.get(key)??''; return !allowed||allowed.includes(v)?v:'';};
  return {q:pick('q').slice(0,200), mode:pick('mode',Object.keys(MODES))||'all',
    corpus_scope:pick('corpus_scope',['all','kaggle-cs','synthetic-cs'])||'all',
    document_type:pick('document_type',['series','map']), map_name:pick('map_name').slice(0,64),
    include_synthetic:query.get('include_synthetic')!=='false'};
}
function toLocation(filters:Filters) {
  const query = new URLSearchParams(Object.entries(filters).filter(([k,v])=>k==='include_synthetic'?v===false:v&&EMPTY[k as keyof Filters]!==v).map(([k,v])=>[k,String(v)]));
  history.replaceState(null,'','#search'+(query.size?'?'+query.toString():''));
}

export function Search() {
  const [draft,setDraft] = useState<Filters>(fromLocation);
  const [applied,setApplied] = useState<Filters>(fromLocation);
  const [page,setPage] = useState(1);
  const [refresh,setRefresh] = useState(0);
  const [state,setState] = useState<State>({kind:'loading'});
  const [index,setIndex] = useState<IndexStatus|null>(null);
  const [maps,setMaps] = useState<string[]>([]);
  const [selected,setSelected] = useState<Doc|null>(null);
  const [openError,setOpenError] = useState('');
  const dialog = useRef<HTMLDialogElement>(null); const opener = useRef<HTMLElement|null>(null);

  useEffect(()=>{const abort=new AbortController();
    getJson('/search/status',abort.signal).then(setIndex).catch(()=>{if(!abort.signal.aborted)setIndex(null);});
    return()=>abort.abort();},[refresh]);

  useEffect(()=>{
    const abort = new AbortController(); setState({kind:'loading'});
    getJson('/search?'+params(applied,page),abort.signal).then((result:Result)=>{
      setState({kind:'result',result});
      const seen=result.facets.map_name?.map(b=>b.value)??[];
      setMaps(previous=>Array.from(new Set([...previous,...seen])).sort());
    }).catch(async(e)=>{
      if(abort.signal.aborted) return;
      const error = e as HttpError;
      if(error.status===422||error.status===500){setState({kind:'error',message:error.status===422?'Некоректні параметри: '+error.message:'Помилка пошукового сервісу. Спробуйте ще раз.'});return;}
      // 503 from search_api, 502/504 from nginx or no connection: the index is unavailable.
      setState({kind:'degraded',reason:error.reason||error.message,fallback:null,fallbackError:''});
      try { const fallback = await getJson('/documents?'+fallbackParams(applied,page),abort.signal);
        if(!abort.signal.aborted) setState({kind:'degraded',reason:error.reason||error.message,fallback,fallbackError:''}); }
      catch(f){ if(!abort.signal.aborted) setState({kind:'degraded',reason:error.reason||error.message,fallback:null,fallbackError:(f as Error).message}); }
    });
    return()=>abort.abort();
  },[applied,page,refresh]);

  useEffect(()=>{if(selected)dialog.current?.showModal();},[selected]);
  function close(){dialog.current?.close();setSelected(null);opener.current?.focus();}
  async function open(id:string){opener.current=document.activeElement as HTMLElement;setOpenError('');
    try{setSelected(await getJson('/documents/'+id,new AbortController().signal));}
    catch(e){setOpenError('Не вдалося відкрити документ: '+(e as Error).message);}}

  const set = <K extends keyof Filters>(key:K, value:Filters[K]) => setDraft(d=>({...d,[key]:value}));
  const submit = (next:Filters) => {const normalized={...next,include_synthetic:next.include_synthetic||next.corpus_scope==='synthetic-cs'};
    setApplied(normalized);toLocation(normalized);setPage(1);setRefresh(v=>v+1);};
  const total = state.kind==='result'?state.result.total:state.kind==='degraded'&&state.fallback?state.fallback.total:0;
  const lastPage = Math.max(1,Math.min(Math.ceil(total/PAGE_SIZE),Math.floor(10000/PAGE_SIZE)));
  const synthetics = draft.corpus_scope==='synthetic-cs';

  return <section className="panel search-panel">
    <div className="panel-title"><h2>Повнотекстовий пошук</h2>
      <span className={'pill index-pill '+(index?.status==='ok'?'ok':'down')} title="Стан індексу Elasticsearch">
        {index?`ELASTICSEARCH · ${fmt(index.documents)} ДОК. · ${index.cluster.health.toUpperCase()}`:'ELASTICSEARCH · НЕДОСТУПНИЙ'}</span></div>
    <form onSubmit={e=>{e.preventDefault();submit(draft);}}>
      <div className="search-row"><label className="search"><span aria-hidden="true">⌕</span>
        <input value={draft.q} onChange={e=>set('q',e.target.value)} maxLength={200} aria-label="Пошуковий запит"
          placeholder="Команда, карта, гравець або турнір: «Vitality Mirage», «s1mple», «IEM Katowice»…"/></label>
        <button className="primary" type="submit">Шукати <span>↗</span></button></div>
      <div className="filters search-filters">
        <label>Режим пошуку<select value={draft.mode} onChange={e=>set('mode',e.target.value)}>{Object.entries(MODES).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
        <label>Корпус<select value={draft.corpus_scope} onChange={e=>set('corpus_scope',e.target.value)}><option value="all">Увесь корпус</option><option value="kaggle-cs">Kaggle (реальні матчі)</option><option value="synthetic-cs">Синтетичний (SDV)</option></select></label>
        <label>Тип документа<select value={draft.document_type} onChange={e=>set('document_type',e.target.value)}><option value="">Усі документи</option><option value="series">Підсумки матчів</option><option value="map">Окремі карти</option></select></label>
        <label>Карта<select value={draft.map_name} onChange={e=>set('map_name',e.target.value)}><option value="">Усі карти</option>{Array.from(new Set([...maps,...(draft.map_name?[draft.map_name]:[])])).map(m=><option key={m} value={m}>{m}</option>)}</select></label>
        <label className="check"><span>Синтетичні записи</span><span className="check-row"><input type="checkbox" checked={draft.include_synthetic||synthetics} disabled={synthetics}
          onChange={e=>set('include_synthetic',e.target.checked)}/>{draft.include_synthetic||synthetics?'Включати':'Виключити'}</span></label>
      </div>
      <div className="filter-help"><p>{MODE_HELP[draft.mode]}</p><button type="button" onClick={()=>{setDraft(EMPTY);submit(EMPTY);}}>Скинути</button></div>
    </form>

    <div className="results-heading" aria-live="polite">
      <span>{state.kind==='loading'?'Пошук…':state.kind==='result'?`${state.result.total_relation==='gte'?'понад ':''}${fmt(state.result.total)} документів`:state.kind==='degraded'?'Резервний режим':'Помилка'}</span>
      {state.kind==='result'&&<small className="timing">Elasticsearch: {state.result.took_ms??'—'} мс · сервіс: {fmt(state.result.elapsed_ms,1)} мс · сортування за релевантністю (_score)</small>}
    </div>

    {state.kind==='result'&&state.result.degraded&&<div className="notice warn" role="status">Відповідь неповна: пошуковий рушій перевищив ліміт часу. Уточніть запит або повторіть пізніше.</div>}
    {state.kind==='error'&&<div className="error" role="alert">{state.message} <button onClick={()=>setRefresh(v=>v+1)}>Повторити</button></div>}
    {state.kind==='degraded'&&<div className="error degraded" role="alert"><strong>Пошуковий індекс тимчасово недоступний.</strong> Показано буквальний пошук MongoDB (без ранжування, підсвічування та фільтра карти; один корпус: {SCOPE[fallbackScope(applied)]}).
      {state.reason&&<small className="block muted">Причина: {state.reason}</small>} <button onClick={()=>setRefresh(v=>v+1)}>Перевірити індекс знову</button></div>}
    {state.kind==='degraded'&&state.fallbackError&&<div className="error" role="alert">Резервний пошук теж недоступний: {state.fallbackError}</div>}
    {openError&&<div className="error" role="alert">{openError}</div>}

    {state.kind==='result'&&state.result.status==='empty'&&<div className="empty"><span>⌕</span><h3>Нічого не знайдено</h3>
      <p>Спробуйте режим «Будь-яке слово» або «З урахуванням опечаток», зніміть фільтри чи увімкніть синтетичні записи.</p></div>}

    <div className="documents" aria-busy={state.kind==='loading'}>
      {state.kind==='result'&&state.result.hits.map(hit=><SearchHit key={hit.id} hit={hit} max={state.result.max_score} open={open}/>)}
      {state.kind==='degraded'&&state.fallback?.items.map(doc=><button className="document" key={doc.id} onClick={()=>void open(doc.id)}>
        <span className={'doc-icon '+doc.metadata.document_type}>{doc.metadata.document_type==='series'?'M':'К'}</span>
        <div><div className="doc-meta">{doc.metadata.document_type==='series'?'ПІДСУМОК МАТЧУ':'РЕЗУЛЬТАТ КАРТИ'} · {doc.metadata.played_at?.slice(0,10)} · без оцінки релевантності</div><h3>{doc.title}</h3></div><span className="arrow">↗</span></button>)}
    </div>
    {(state.kind==='result'||state.kind==='degraded')&&total>0&&<nav className="pagination" aria-label="Сторінки результатів пошуку">
      <span>Сторінка {page} із {lastPage}{total>10000?' (перші 10 000 результатів)':''}</span>
      <div><button disabled={page===1} onClick={()=>setPage(p=>p-1)}>← Назад</button><button disabled={page>=lastPage} onClick={()=>setPage(p=>p+1)}>Далі →</button></div></nav>}
    <dialog ref={dialog} aria-labelledby="document-title" onCancel={e=>{e.preventDefault();close();}} onClose={()=>{setSelected(null);opener.current?.focus();}}>{selected&&<DocumentView doc={selected} close={close}/>}</dialog>
  </section>;
}

function SearchHit({hit,max,open}:{hit:Hit;max:number|null;open:(id:string)=>void}) {
  const fragments = Object.entries(hit.highlights).filter(([field])=>!['title','team1','team2','map_name'].includes(field));
  const relative = hit.score!==null&&max?Math.max(4,Math.round(hit.score/max*100)):0;
  return <button className={'document search-hit'+(hit.is_synthetic?' synthetic':'')} onClick={()=>open(hit.id)}>
    <span className={'doc-icon '+hit.document_type}>{hit.document_type==='series'?'M':'К'}</span>
    <div className="hit-body">
      <div className="doc-meta">{hit.document_type==='series'?'ПІДСУМОК МАТЧУ':'РЕЗУЛЬТАТ КАРТИ'} <span>·</span> {hit.played_at?.slice(0,10)??'дата невідома'}
        {hit.map_name&&<><span>·</span>{hit.map_name}</>}
        {hit.is_synthetic?<em className="badge synthetic" title="Згенеровано SDV для навантажувального тестування; не описує реальний матч">СИНТЕТИЧНИЙ ЗАПИС</em>:<em className="badge real">KAGGLE</em>}</div>
      <h3>{hit.highlights.title?<Highlighted text={hit.highlights.title[0]}/>:hit.title}</h3>
      {fragments.length>0?<dl className="fragments">{fragments.map(([field,parts])=><React.Fragment key={field}>
        <dt>{FIELD[field]??field}</dt><dd>{parts.map((p,i)=><span key={i} className="fragment"><Highlighted text={p}/>{i<parts.length-1?' … ':''}</span>)}</dd></React.Fragment>)}</dl>
        :<p className="snippet">{hit.snippet}</p>}
    </div>
    <span className="score" title="Оцінка релевантності Elasticsearch (BM25, _score)"><small>_score</small><strong>{hit.score===null?'—':hit.score.toFixed(2)}</strong><i style={{width:relative+'%'}}/></span>
  </button>;
}
