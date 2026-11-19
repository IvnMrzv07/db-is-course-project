import React from 'react';

export type PlayerStat = {team:1|2; slot:number; player_id:string|null; name:string; kills:number|null; deaths:number|null; assists:number|null; adr:number|null; kast:number|null; kddiff:number|null};
// v1 fields are strings; template v2 adds JSON-typed fields (numbers, null, players list).
export type DocMetadata = {document_type:string; tournament:string; team1:string; team2:string; played_at:string; players?:PlayerStat[]; [key:string]:unknown};
export type Doc = {id:string; title:string; text?:string; source_url:string; source_id:string; metadata:DocMetadata};
const labels:Record<string,string> = {match_id:'ID матчу',game_id:'ID карти',map_name:'Карта',best_of:'Формат (best of)',score1:'Рахунок команди 1',score2:'Рахунок команди 2',winner_team:'Переможець',snapshot_sha256:'Контрольна сума набору',template_version:'Версія шаблону',generated_from_dataset:'Сформовано з датасету',source_timezone:'Часовий пояс джерела'};
const shown=(value:unknown)=>value===null||value===undefined||value===''?'Не вказано':value==='unspecified'?'Не вказано':value==='true'?'Так':value==='false'?'Ні':String(value);

// Only split the known v1 template into paragraphs; never infer missing statistics.
export function textSections(text:string) {
  const prefix = text.match(/^.*? on \d{4}-\d{2}-\d{2}\.(?: Map: .*?\.)?(?: (?:Map|Series) score: \d+-\d+\.)?/);
  if (!prefix) return {summary:text,players:[] as string[]};
  const rest=text.slice(prefix[0].length).trim();
  return {summary:prefix[0],players:rest?rest.split(/(?<=\.)\s+(?=[^:]+:\s+-?\d+(?:\.\d+)?\s+(?:kills|deaths|assists|adr|kast))/):[]};
}

export function DocumentView({doc,close}:{doc:Doc;close:()=>void}) {
  const m=doc.metadata;
  const {summary,players}=textSections(doc.text||'');
  const date=m.played_at?.slice(0,10).split('-').reverse().join('.');
  return <article className="document-view">
    <div className="dialog-toolbar"><span className="pill">{m.document_type==='series'?'ПІДСУМОК МАТЧУ':'РЕЗУЛЬТАТ КАРТИ'}</span><button autoFocus aria-label="Закрити документ" onClick={close}>✕</button></div>
    <div className="dialog-body">
      <p className="document-tournament">{m.tournament}</p>
      <h2 id="document-title">{m.team1} <span className="versus">vs</span> {m.team2}</h2>
      <p className="document-date"><time dateTime={m.played_at}>{date}</time><span>Часовий пояс у джерелі не вказано</span></p>
      <section className="match-summary" aria-label="Підсумок"><h3>Про матч</h3><p lang="en">{summary}</p></section>
      {players.length>0&&<section aria-labelledby="player-title"><h3 id="player-title">Статистика зі джерела</h3><div className="player-records" lang="en">{players.map((player,index)=><p key={index}>{player}</p>)}</div></section>}
      <details className="document-details"><summary>Оригінальний текст документа</summary><p className="full-text" lang="en">{doc.text}</p></details>
      <section className="document-source"><h3>Походження</h3><p>Локальний набір Counter-Strike Pro Matches · фактологічний опис англійською.</p><a href={doc.source_url} target="_blank" rel="noreferrer">Переглянути датасет на Kaggle ↗<span className="sr-only"> (у новій вкладці)</span></a></section>
      <details className="document-details"><summary>Технічні дані</summary><dl><dt>ID документа</dt><dd>{doc.id}</dd><dt>Ключ джерела</dt><dd>{doc.source_id}</dd>{Object.entries(labels).filter(([key])=>key in m).map(([key,label])=><React.Fragment key={key}><dt>{label}</dt><dd>{shown(m[key])}</dd></React.Fragment>)}</dl></details>
    </div>
  </article>;
}
