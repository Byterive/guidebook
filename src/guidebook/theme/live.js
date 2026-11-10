/* Banner behaviour. Static (file://): shows the command to copy. Served by `guidebook serve` (http://127.0.0.1): also shows live status and a working "Check and update" button. */
(function(){
 var b=document.getElementById('gb-banner');if(!b)return;
 var msg=b.querySelector('.gb-msg'),cmd=b.querySelector('.gb-cmd'),copy=b.querySelector('.gb-copy'),live=b.querySelector('.gb-live'),go=b.querySelector('.gb-go');
 if(copy)copy.addEventListener('click',function(){var t=cmd.textContent;
  if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(function(){copy.textContent='Copied'},function(){copy.textContent='Select and copy'})}else{copy.textContent='Select and copy'}});
 if(location.protocol!=='http:')return;
 function show(s){
  var n=(s.changed_sources||[]).length;
  msg.textContent=s.ok?'This guide is up to date.':('Out of date: '+s.stale.length+' page'+(s.stale.length===1?'':'s')+' stale, '+n+' source'+(n===1?'':'s')+' changed since the last build'+(s.html!=='fresh'?'; html '+s.html:'')+'.');
  if(s.built_at)msg.textContent+=' Last built '+s.built_at+'.';
  if(live)live.hidden=false}
 fetch('/__guidebook/status').then(function(r){return r.json()}).then(show).catch(function(){});
 if(go)go.addEventListener('click',function(){
  go.disabled=true;go.textContent='Updating...';
  fetch('/__guidebook/update',{method:'POST',headers:{'X-Guidebook':'1'}}).then(function(r){return r.json()}).then(function(d){
   if(d.error){go.textContent='Failed: '+d.error;go.disabled=false;return}
   go.textContent=d.nothing_to_do?'Nothing to update':'Updated '+d.written.length+' page'+(d.written.length===1?'':'s')+(d.proposed.length?' ('+d.proposed.length+' proposal'+(d.proposed.length===1?'':'s')+' waiting)':'');
   if(d.status)show(d.status);
   if(!d.nothing_to_do)setTimeout(function(){location.reload()},900);else go.disabled=false
  }).catch(function(){go.textContent='Could not reach the server';go.disabled=false})})
})();
