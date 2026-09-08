/* Keep every filtered row available while mounting only the working window. */
(function () {
  'use strict';
  window.TdpInvoiceVirtualTable = function (scroll, lines, renderRow) {
    if (!scroll || lines.length <= 2000) return null;
    var body=scroll.querySelector('tbody'), cols=scroll.querySelector('thead tr').cells.length;
    function key(row){return row.id==null?'empty-'+row.invoice_id:String(row.id);}
    var cache=new Map(), heights=new Map(), index=new Map(lines.map((r,i)=>[key(r),i]));
    var offsets=[], start=-1, end=-1, frame, disposed=false;
    function offsetsForRows(){offsets=[0];for(var i=0;i<lines.length;i++)offsets.push(offsets[i]+(heights.get(i)||112));}
    function locate(y){var lo=0,hi=lines.length;while(lo<hi){var mid=(lo+hi)>>1;if(offsets[mid+1]<y)lo=mid+1;else hi=mid;}return Math.min(lo,lines.length-1);}
    function node(i){if(!cache.has(i)){var t=document.createElement('tbody');t.innerHTML=renderRow(lines[i]);cache.set(i,t.firstElementChild);}return cache.get(i);}
    function spacer(height){var row=document.createElement('tr'),cell=document.createElement('td');row.className='invoice-virtual-spacer';row.setAttribute('aria-hidden','true');cell.colSpan=cols;cell.style.cssText='height:'+Math.max(0,height)+'px;padding:0;border:0;';row.append(cell);return row;}
    function paint(force){
      if(disposed||!scroll.isConnected)return;
      var anchor=locate(scroll.scrollTop), delta=scroll.scrollTop-offsets[anchor];
      var next=Math.max(0,anchor-20), last=Math.min(lines.length,next+80);
      if(!force && anchor>=start+10 && anchor<end-30)return;
      start=next;end=last;
      var active=document.activeElement, selection=active?.selectionStart, selectionEnd=active?.selectionEnd;
      var fragment=document.createDocumentFragment();fragment.append(spacer(offsets[start]));
      for(var i=start;i<end;i++)fragment.append(node(i));
      fragment.append(spacer(offsets[lines.length]-offsets[end]));body.replaceChildren(fragment);
      for(var i=start;i<end;i++)heights.set(i,node(i).getBoundingClientRect().height);
      offsetsForRows();body.firstElementChild.firstElementChild.style.height=offsets[start]+'px';body.lastElementChild.firstElementChild.style.height=(offsets[lines.length]-offsets[end])+'px';
      scroll.scrollTop=offsets[anchor]+delta;
      if(active?.isConnected && body.contains(active)){active.focus({preventScroll:true});if(selection!=null)try{active.setSelectionRange(selection,selectionEnd);}catch(ignore){}}
      // Detached drafts and checked rows survive scrolling. Unedited rows can be rebuilt.
      for(var [i,row] of cache)if((i<start-80||i>end+80)&&!row.querySelector('[data-editing-id],input:checked'))cache.delete(i);
    }
    function schedule(){cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>paint(false));}
    offsetsForRows();scroll.style.overflowAnchor='none';scroll.addEventListener('scroll',schedule);paint(true);
    return {
      nodes:()=>Array.from(cache.values()),
      snapshot:()=>Array.from(heights,([i,h])=>[key(lines[i]),h]),
      checked:()=>Array.from(cache.values()).flatMap(r=>Array.from(r.querySelectorAll('.invoice-group-select:checked'))),
      reveal:function(id){var i=index.get(String(id));if(i==null)return null;scroll.scrollTop=offsets[i];paint(true);return node(i);},
      restore:function(top,left,drafts,choices,previousHeights){
        (previousHeights||[]).forEach(([id,h])=>{var i=index.get(id);if(i!=null)heights.set(i,h);});offsetsForRows();
        drafts.forEach(cell=>{var i=index.get(cell.dataset.editingId);if(i!=null)node(i).querySelector('.invoice-mapping-cell').replaceWith(cell);});
        choices.forEach(id=>{var i=index.get(String(id));if(i!=null){var box=node(i).querySelector('.invoice-group-select');if(box)box.checked=true;}});
        scroll.scrollTop=top;scroll.scrollLeft=left;paint(true);
      },
      dispose:function(){disposed=true;cancelAnimationFrame(frame);scroll.removeEventListener('scroll',schedule);}
    };
  };
})();
