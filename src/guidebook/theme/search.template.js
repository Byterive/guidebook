
const ENTRIES = __ENTRIES__;
function find(q){q=q.toLowerCase().split(/\s+/).filter(Boolean);if(!q.length)return[];
 return ENTRIES.map(e=>{let s=0;for(const w of q){if(e.t.toLowerCase().includes(w))s+=5;if(e.s.toLowerCase().includes(w))s+=3;if(e.x.includes(w))s+=1;else{s=-1e9}}return[s,e]})
  .filter(r=>r[0]>0).sort((a,b)=>b[0]-a[0]).slice(0,12).map(r=>r[1])}
document.addEventListener('DOMContentLoaded',()=>{
 const q=document.getElementById('q'),r=document.getElementById('res');
 if(q){q.addEventListener('input',()=>{r.innerHTML=find(q.value).map(e=>'<a href="'+ROOT+e.u+'">'+e.t+'<small>'+e.s+'</small></a>').join('')});
  document.addEventListener('keydown',ev=>{if(ev.key==='/'&&document.activeElement!==q){ev.preventDefault();q.focus()}if(ev.key==='Escape'){q.value='';r.innerHTML='';document.querySelectorAll('details.dd[open]').forEach(d=>d.open=false)}})}
 const dds=[...document.querySelectorAll('details.dd')],wide=()=>window.matchMedia('(min-width:901px)').matches;
 dds.forEach(d=>{d.addEventListener('toggle',()=>{if(d.open)dds.forEach(o=>{if(o!==d)o.open=false})});
  d.addEventListener('mouseenter',()=>{if(wide())d.open=true});d.addEventListener('mouseleave',()=>{if(wide())d.open=false})});
 document.addEventListener('click',ev=>{if(!ev.target.closest('details.dd'))dds.forEach(d=>d.open=false);if(r&&!ev.target.closest('#res')&&ev.target!==q)r.innerHTML=''});
 const b=document.getElementById('burger'),h=document.querySelector('header.top');if(b)b.addEventListener('click',()=>h.classList.toggle('open'));
 const t=document.getElementById('theme');if(t)t.addEventListener('click',()=>{const cur=document.documentElement.dataset.theme||(window.matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
  const nxt=cur==='dark'?'light':'dark';document.documentElement.dataset.theme=nxt;try{localStorage.setItem('sgtheme',nxt)}catch(e){}});
});
try{const s=localStorage.getItem('sgtheme');if(s)document.documentElement.dataset.theme=s}catch(e){}
