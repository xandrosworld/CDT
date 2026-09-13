(function (root) {
  'use strict';
  function wrap(text, width, measure) {
    var lines = [], line = '';
    String(text == null ? '' : text).split(/\n/).forEach(function (paragraph) {
      paragraph.split(/\s+/).filter(Boolean).forEach(function (word) {
        if (line && measure(line + ' ' + word) > width) { lines.push(line); line = ''; }
        for (var character of word) {
          if (measure(line + character) > width && line) { lines.push(line); line = ''; }
          line += character;
        }
        line += ' ';
      });
      lines.push(line.trimEnd()); line = '';
    });
    return lines.length ? lines : [''];
  }
  function layout(group, options, measure) {
    var items = group.items || [], fontSize = 26, padding = 8;
    var columns = [{key:'kitchen',label:'Bếp',max:160}, {key:'product_name',label:'Tên hàng',max:290},
      {key:'order_qty',label:'SL',max:160}, {key:'unit',label:'ĐVT',max:88}];
    if (items.some(function(r) { return (r.work_date || options.date) !== options.date; })) columns.splice(1,0,{key:'work_date',label:'Ngày',max:156});
    if (items.some(function(r) { return r.supplier && r.supplier !== group.supplier; })) columns.push({key:'supplier',label:'NCC',max:135});
    columns.push({key:'note',label:'Ghi chú',max:190});
    var rows = items.map(function(r) { return Object.assign({},r,{
      order_qty:options.quantity(r.order_qty == null ? r.required_qty : r.order_qty),
      work_date:options.dateText(r.work_date || options.date)
    }); });
    columns.forEach(function(c) {
      c.width = Math.min(c.max,Math.max(measure(c.label),...rows.map(function(r) {return measure(String(r[c.key] || ''));}))+padding*2);
      if(c.key==='note')c.width=Math.max(115,c.width);
    });
    var total = columns.reduce(function(s,c) {return s+c.width;},0);
    ['product_name','note','kitchen','supplier'].forEach(function(key) {
      var c=columns.find(function(c) {return c.key===key;});
      if (!c || total<=700) return;
      var cut=Math.min(total-700,Math.max(0,c.width-(key==='product_name'?155:key==='note'?115:75)));
      c.width-=cut; total-=cut;
    });
    var headerLines=wrap('NCC '+group.supplier+' · '+options.dateText(options.date),total,measure);
    var top=42+headerLines.length*32+12;
    rows.forEach(function(r) {
      r.cells=columns.map(function(c) { return wrap(r[c.key],c.width-padding*2,measure); });
      r.height=Math.max(48,...r.cells.map(function(lines){return lines.length*32+padding*2;}));
    });
    return {columns:columns,rows:rows,width:total+16,height:top+44+rows.reduce(function(s,r){return s+r.height;},0)+8,
      top:top,headerLines:headerLines,fontSize:fontSize,padding:padding};
  }
  async function blob(group, options) {
    var canvas=document.createElement('canvas'), ctx=canvas.getContext('2d');
    if (!ctx) throw new Error('Trình duyệt không tạo được ảnh NCC.');
    ctx.font='26px Arial, sans-serif';
    var plan=layout(group,options,function(t){return ctx.measureText(t).width;});
    var scale=Math.min(2,30000/plan.height);
    canvas.width=Math.ceil(plan.width*scale);canvas.height=Math.ceil(plan.height*scale);
    ctx.scale(scale,scale);ctx.fillStyle='#fff';ctx.fillRect(0,0,plan.width,plan.height);
    ctx.fillStyle='#000';ctx.textBaseline='middle';ctx.textAlign='center';ctx.font='24px Arial, sans-serif';
    ctx.fillText('ĐƠN ĐẶT HÀNG',plan.width/2,20);
    ctx.font='26px Arial, sans-serif';
    plan.headerLines.forEach(function(t,i){ctx.fillText(t,plan.width/2,52+i*32);});
    var left=8,y=plan.top,x=left;
    ctx.font='22px Arial, sans-serif';
    plan.columns.forEach(function(c){ctx.fillText(c.label,x+c.width/2,y+22);x+=c.width;});
    y+=44;var edges=[plan.top,y];
    plan.rows.forEach(function(r) {
      x=left;
      plan.columns.forEach(function(c,i) {
        ctx.font=(c.key==='order_qty'?'bold ':'')+'26px Arial, sans-serif';
        ctx.textAlign=c.key==='product_name'||c.key==='note'?'left':'center';
        var tx=ctx.textAlign==='left'?x+plan.padding:x+c.width/2;
        r.cells[i].forEach(function(t,j){ctx.fillText(t,tx,y+r.height/2+(j-(r.cells[i].length-1)/2)*32);});
        x+=c.width;
      });
      y+=r.height;edges.push(y);
    });
    ctx.strokeStyle='#000';ctx.lineWidth=0.65;ctx.beginPath();
    x=left;ctx.moveTo(x,plan.top);ctx.lineTo(x,y);
    plan.columns.forEach(function(c){x+=c.width;ctx.moveTo(x,plan.top);ctx.lineTo(x,y);});
    edges.forEach(function(edge){ctx.moveTo(left,edge);ctx.lineTo(x,edge);});ctx.stroke();
    return new Promise(function(resolve,reject){canvas.toBlob(function(image){image?resolve(image):reject(new Error('Không tạo được ảnh NCC.'));},'image/png');});
  }
  var api={layout:layout,wrap:wrap,blob:blob};
  if (typeof module!=='undefined' && module.exports) module.exports=api;
  root.TdpSupplierImage=api;
})(typeof window==='undefined'?globalThis:window);
