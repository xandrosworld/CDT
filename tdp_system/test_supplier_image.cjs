const assert=require('assert/strict');
const renderer=require('./static/supplier-image.js');
const measure=text=>String(text).length*13;
const options={date:'2026-09-13',dateText:x=>x,quantity:x=>String(x)};
const group={supplier:'Hương',items:[
 {kitchen:'LSVINA',product_name:'Thịt heo vai sấn',order_qty:29.5,unit:'Kg',work_date:'2026-09-13',supplier:'Hương',note:''},
 {kitchen:'NHUAHP',product_name:'Thịt heo xay',order_qty:1.1,unit:'Kg',work_date:'2026-09-13',supplier:'Hương',note:''}
]};
let plan=renderer.layout(group,options,measure);
assert(plan.width<=716);assert.equal(plan.rows.length,2);
assert.deepEqual(plan.columns.map(c=>c.key),['kitchen','product_name','order_qty','unit','note']);
assert(plan.columns.find(c=>c.key==='note').width>=90, 'Blank notes must retain writing space');
const long={...group,items:[{...group.items[0],work_date:'2026-09-12',supplier:'NCC khác',note:'Giao đến cửa số 3, gọi trước khi giao. Không trộn với đơn buổi chiều.'}]};
plan=renderer.layout(long,options,measure);
for(const key of ['work_date','supplier','note'])assert(plan.columns.some(c=>c.key===key));
plan.columns.forEach((c,i)=>{
 const text=String(plan.rows[0][c.key]);
 assert.equal(plan.rows[0].cells[i].join('').replace(/\s/g,''),text.replace(/\s/g,''));
 plan.rows[0].cells[i].forEach(line=>assert(measure(line.trimEnd())<=c.width-16));
});
assert.equal(renderer.wrap('Tên hàng rất dài không được mất chữ',80,measure).join('').replace(/\s/g,''),'Tênhàngrấtdàikhôngđượcmấtchữ');
console.log('Supplier image: compact columns, all rows, varied dates/suppliers/notes, no truncated text passed.');
