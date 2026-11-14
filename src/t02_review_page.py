"""Small Vietnamese review UI using the shared review CSV contract."""
from __future__ import annotations

import base64
import html
import json
from pathlib import Path

import pandas as pd


def render(queue: pd.DataFrame, target: Path, image_root: Path, reviewed: pd.DataFrame | None = None) -> None:
    saved = {} if reviewed is None else reviewed.set_index("item_id").to_dict("index")
    cards = []
    for row in queue.to_dict("records"):
        image = image_root / row["evidence_path"]
        src = "data:image/jpeg;base64," + base64.b64encode(image.read_bytes()).decode()
        item = html.escape(row["item_id"])
        suggestion = "Cần chụp lại" if row["suggested_action"] == "RECAPTURE" else "Vẫn dùng được"
        cards.append(f'''<article class="card" data-item="{item}">
<h2>{row['rank']}. {item}</h2><img src="{src}" alt="{item}">
<p><b>Máy đề xuất:</b> {suggestion}</p><p>{html.escape(str(row['reason']))}</p>
<label>Bạn quyết định thế nào?<select class="action"><option value="">— Chưa duyệt —</option>
<option value="KEEP">Vẫn dùng được — giữ ảnh</option><option value="RECAPTURE">Lỗi nặng — cần chụp lại</option>
<option value="HOLD">Chưa quyết định được — để xem lại</option></select></label>
<label>Lý do (có thể bỏ trống)<input class="note"></label></article>''')
    page = '''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Duyệt ảnh T02</title><style>body{font:16px/1.6 system-ui;margin:24px;background:#eff3f5;color:#18313a}
header{background:white;padding:20px;border-radius:12px;max-width:1000px;margin:auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px;max-width:1200px;margin:20px auto}
.card{background:white;padding:18px;border:1px solid #c4d4d7;border-radius:12px}img{width:100%}label{display:block;margin:12px 0}select,input,button{font:inherit;padding:10px;box-sizing:border-box}select,input{width:100%}button{background:#076c61;color:white;border:0;border-radius:8px;cursor:pointer}h2{font-size:20px}</style>
<header><h1>Duyệt 20 ảnh máy ưu tiên</h1><p>Xem ảnh rồi chọn “giữ ảnh”, “cần chụp lại” hoặc “để xem lại”. Đây là bước duyệt đề xuất của máy, khác với bộ nhãn đối chiếu bạn đã tạo.</p>
<label>Tên người duyệt<input id="reviewer" placeholder="Bạn tự nhập tên"></label>
<button id="export">Tải kết quả duyệt (CSV)</button><p id="status"></p>
<p>Sau khi tải: chép file <b>review_queue_reviewed.csv</b> vào cùng thư mục với trang này, rồi chạy lại PoC. Hệ thống sẽ áp quyết định và ghi nhật ký. Bản sao trong trình duyệt giúp giữ lựa chọn nếu bạn tải lại trang.</p></header>
<div class="grid">__CARDS__</div><script>
const rows=__ROWS__, saved=__SAVED__, key='t02-review-'+__KEY__;
let progress={};try{progress=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){}
const cards=[...document.querySelectorAll('.card')];
document.getElementById('reviewer').value=progress.reviewer||'';
cards.forEach((c,i)=>{const old=saved[rows[i].item_id]||{},p=(progress.items||{})[rows[i].item_id];
 const action=old.reviewer_decision==='escalate'?'HOLD':old.reviewer_decision==='approve'?rows[i].suggested_action:['edit','reject'].includes(old.reviewer_decision)?old.override_value:'';
 c.querySelector('.action').value=p?.action??action;c.querySelector('.note').value=p?.note??old.review_note??'';
 if(!document.getElementById('reviewer').value&&old.reviewer)document.getElementById('reviewer').value=old.reviewer;
});
function store(){const items={};cards.forEach((c,i)=>items[rows[i].item_id]={action:c.querySelector('.action').value,note:c.querySelector('.note').value});
 try{localStorage.setItem(key,JSON.stringify({reviewer:document.getElementById('reviewer').value,items}))}catch(e){document.getElementById('status').textContent='Không lưu được tiến độ trên trình duyệt; hãy tải CSV.'}}
document.addEventListener('change',store);document.addEventListener('input',store);
const cols=['rank','item_id','score','reason','suggested_action','slice','evidence_path','reviewer','reviewer_decision','override_value','review_note','reviewed_at'];
const cell=v=>'"'+String(v??'').replaceAll('"','""')+'"';
document.getElementById('export').onclick=()=>{const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer){alert('Nhập tên của bạn trước.');return}
 const now=new Date().toISOString();let count=0;
 const lines=cards.map((c,i)=>{const r={...rows[i]},action=c.querySelector('.action').value;r.review_note=c.querySelector('.note').value;r.override_value='';
 r.reviewer=action?reviewer:'';r.reviewed_at=action?now:'';r.reviewer_decision=action==='HOLD'?'escalate':action===r.suggested_action?'approve':action?'edit':'';
 if(r.reviewer_decision==='edit')r.override_value=action;if(action)count++;return cols.map(k=>cell(r[k])).join(',')});
 const url=URL.createObjectURL(new Blob(['\\uFEFF'+[cols.join(','),...lines].join('\\r\\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='review_queue_reviewed.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 document.getElementById('status').textContent=`Đã xuất ${count}/${rows.length} ảnh có quyết định.`;store()};
</script></html>'''
    from .common.io import sha256_text
    records = queue.to_dict("records")
    # Include predictions in the storage key: a changed run must not silently reuse approvals.
    key = sha256_text(json.dumps(records, sort_keys=True))
    page = page.replace("__CARDS__", "\n".join(cards))
    page = page.replace("__ROWS__", json.dumps(records, ensure_ascii=True))
    page = page.replace("__SAVED__", json.dumps(saved, ensure_ascii=True).replace("<", "\\u003c"))
    page = page.replace("__KEY__", json.dumps(key))
    target.write_text(page, encoding="utf-8")
