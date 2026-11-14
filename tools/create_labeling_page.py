"""Build an offline, initially blank T02 manual-labeling page (stdlib only).

The rubric was approved by the student: only severity 2 is a defect.
This creates internal manual reference labels, never instructor ground truth.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/t02_raw_qc"

PAGE = r'''<!doctype html>
<html lang="vi"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>T02 · Gán nhãn thủ công nội bộ</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#eff3f5;color:#182c3b;font:16px/1.6 system-ui,sans-serif}
main{max-width:1200px;margin:auto;padding:24px}h1{margin:0;font-size:26px}.panel{background:white;border:1px solid #ced9df;border-radius:12px;padding:20px;margin:16px 0}
.grid{display:grid;grid-template-columns:1.4fr 1fr;gap:24px}img{display:block;width:100%;height:auto;background:#222;image-rendering:auto}
label{display:block;margin:12px 0}input,select,textarea,button{font:inherit;padding:9px;border:1px solid #aabdc8;border-radius:6px}input,select,textarea{width:100%}
button{cursor:pointer;background:#fff;margin:5px 5px 5px 0}button.primary{background:#076c61;color:white}button:disabled{opacity:.5;cursor:default}
.muted{color:#546672}.notice{color:#895000}#message{min-height:28px;font-weight:600}progress{width:100%}details{margin-top:14px}li{margin:5px 0}
.choices{display:grid;gap:8px}.choice{display:flex;gap:12px;align-items:flex-start;padding:12px;border:1px solid #b7c9d1;border-radius:9px;margin:0;cursor:pointer}.choice:has(input:checked){background:#e5f5f0;border:2px solid #076c61;padding:11px}.choice input{width:auto;margin-top:6px}.choice small{display:block;color:#546672}.step{font-weight:700;font-size:18px;margin:16px 0 10px}#savedState{font-weight:600;color:#076c61}.tools{display:flex;gap:16px;flex-wrap:wrap}.tools>label{flex:1;min-width:200px}.panel p{margin:8px 0}.primary{min-height:48px}
@media(max-width:750px){.grid{grid-template-columns:1fr}main{padding:12px}}
</style><main>
<h1>Xem ảnh và chọn chất lượng</h1>
<p>Mỗi ảnh: chọn chất lượng → chọn lỗi nếu có → bấm <b>Lưu và sang ảnh sau</b>.</p>
<div class="panel">
<strong>Nhìn gì để quyết định?</strong>
<p>Bạn còn nhìn rõ các vật và đường nét trong ảnh không? Có vùng nào bị mờ, sáng chói hoặc tối đến mức không nhìn ra chi tiết không?</p>
<p>Nếu phân vân, bấm <b>Để xem lại</b>. Ảnh đó sẽ được để riêng để bạn quay lại sau, chưa tính là tốt hay lỗi.</p>
<details><summary>Xem quy tắc của bộ nhãn</summary><p>Ảnh tốt = mức 0; lỗi nhẹ, vẫn dùng được = mức 1; lỗi nặng, cần chụp lại = mức 2. Chỉ mức 2 tính là ảnh lỗi khi đối chiếu kết quả. Ảnh đêm không tự động là lỗi. Nhiều lỗi thì chọn lỗi ảnh hưởng nhiều nhất; ghi lỗi phụ nếu cần.</p>
<p>96 ảnh giả lập, do bạn tự đánh giá; không phải đáp án chính thức của giảng viên. Giữ nguyên hai phần dữ liệu: dev để thử và chọn ngưỡng, eval để đối chiếu sau khi chốt ngưỡng. Không xem điểm dự đoán khi gán nhãn.</p></details>
</div>
<div class="panel">
<div class="tools"><label>Tên của bạn<input id="annotator" autocomplete="off" placeholder="Nhập tên một lần"></label>
<label>Phần dữ liệu<select id="split"><option value="dev">Phần 1 · Làm trước (dev, 56 ảnh)</option><option value="eval">Phần 2 · Đối chiếu sau (eval, 40 ảnh)</option></select></label></div>
<p id="progressText"></p><progress id="progress" max="96" value="0"></progress>
<details><summary>Lưu tiến độ để hôm khác làm tiếp</summary><button id="backup">Tải file lưu tiến độ (JSON)</button><label>Mở lại file tiến độ đã tải<input id="restore" type="file" accept="application/json,.json"></label>
<p class="muted">Trang tự lưu trên trình duyệt nếu được phép. Vẫn nên tải file tiến độ sau mỗi buổi để tránh mất dữ liệu.</p></details>
</div>
<div class="panel grid"><div>
<h2 id="imageTitle"></h2><img id="photo" alt="Ảnh cần gán nhãn">
<p class="muted">Ảnh hiển thị phóng lớn. Bấm ảnh để mở bản gốc trong tab riêng.</p>
<p id="savedState"></p><button id="prev">← Ảnh trước</button><button id="next">Ảnh sau →</button><button id="unlabeled">Tìm ảnh chưa làm</button><button id="revisit">Tìm ảnh để xem lại</button>
</div><div>
<p class="step">1. Ảnh này dùng được không?</p>
<div class="choices">
<label class="choice"><input type="radio" name="quality" value="0"><span><b>Ảnh tốt</b><small>Nhìn rõ, không thấy lỗi đáng kể.</small></span></label>
<label class="choice"><input type="radio" name="quality" value="1"><span><b>Có lỗi nhẹ, vẫn dùng được</b><small>Hơi mờ / tối / lóa, nhưng vẫn nhìn ra chi tiết cần thiết.</small></span></label>
<label class="choice"><input type="radio" name="quality" value="2"><span><b>Lỗi nặng, cần chụp lại</b><small>Mất chi tiết quan trọng, khó dùng để quan sát hoặc gán nhãn.</small></span></label>
</div>
<div id="kindSection" hidden><p class="step">2. Lỗi nào ảnh hưởng nhiều nhất?</p>
<div class="choices">
<label class="choice"><input type="radio" name="kind" value="blur"><span><b>Bị mờ / nhòe</b><small>Ví dụ: các đường viền nhòe, khó phân biệt vật với nền.</small></span></label>
<label class="choice"><input type="radio" name="kind" value="glare"><span><b>Bị lóa / chói sáng</b><small>Ví dụ: có mảng trắng sáng che mất vật hoặc chi tiết.</small></span></label>
<label class="choice"><input type="radio" name="kind" value="dark"><span><b>Bị tối, mất chi tiết</b><small>Ví dụ: vùng tối đen khiến bạn không nhìn ra vật trong đó.</small></span></label>
<label class="choice"><input type="radio" name="kind" value="compression"><span><b>Bị vỡ hình / bệt màu</b><small>Ví dụ: xuất hiện ô vuông, viền răng cưa hoặc mảng màu bị bệt do nén ảnh.</small></span></label>
</div></div>
<label>Ghi chú (có thể bỏ trống)<textarea id="note" rows="2" placeholder="Ví dụ: mờ nhiều, có thêm vùng bị lóa..."></textarea></label>
<button class="primary" id="save">Lưu và sang ảnh sau →</button><button id="defer">Để xem lại</button><p id="message" role="status"></p>
</div></div>
<div class="panel"><button class="primary" id="export">Tải kết quả gán nhãn (CSV)</button>
<p>CSV chứa cả 96 ảnh. Ảnh chưa làm hoặc để xem lại chưa được tính là tốt hay lỗi. Hãy làm đủ phần dữ liệu cần đối chiếu trước khi tính kết quả.</p></div>
</main><script>
const items=__ITEMS__, dataset=__HASH__, policy='t02-internal-severity2-v1';
const $=id=>document.getElementById(id), key='t02-labels-'+dataset;
let labels={}, index=0, savedAnnotator='';
try{const s=JSON.parse(localStorage.getItem(key)||'{}');labels=s.labels||{};savedAnnotator=s.annotator||''}catch(e){}
$('annotator').value=savedAnnotator;
const pool=()=>items.filter(x=>x.split===$('split').value);
const current=()=>pool()[index];
function persist(){try{localStorage.setItem(key,JSON.stringify({labels,annotator:$('annotator').value}))}catch(e){$('message').textContent='Không lưu được trong trình duyệt; hãy tải bản sao JSON.'}}
function progress(){let done=0,uncertain=0;for(const x of items){if(labels[x.image_id]?.status==='labeled')done++;if(labels[x.image_id]?.status==='uncertain')uncertain++}
 $('progress').value=done;$('progressText').textContent=`Đã làm ${done}/${items.length} ảnh · Để xem lại: ${uncertain} · Chưa làm: ${items.length-done-uncertain}`}
const selected=name=>document.querySelector(`input[name="${name}"]:checked`)?.value??'';
function showKind(){$('kindSection').hidden=!['1','2'].includes(selected('quality'))}
document.querySelectorAll('input[name="quality"]').forEach(el=>el.onchange=showKind);
function show(){const rows=pool();index=Math.max(0,Math.min(index,rows.length-1));const x=current(),v=labels[x.image_id]||{};
 $('imageTitle').textContent=`${x.image_id} · ${x.split} · ${index+1}/${rows.length}`;$('photo').src=x.image;
 document.querySelectorAll('input[name="quality"]').forEach(el=>el.checked=v.status==='labeled'&&el.value===v.severity);
 document.querySelectorAll('input[name="kind"]').forEach(el=>el.checked=el.value===v.defect_type);
 $('note').value=v.note??'';showKind();
 const qualityNames={'0':'Ảnh tốt','1':'Có lỗi nhẹ, vẫn dùng được','2':'Lỗi nặng, cần chụp lại'};
 $('savedState').textContent=v.status==='labeled'?'Đã lưu: '+qualityNames[v.severity]:v.status==='uncertain'?'Đã đánh dấu: Để xem lại':'Ảnh này chưa làm.';
 $('prev').disabled=index===0;$('next').disabled=index===rows.length-1;$('message').textContent='';progress()}
function save(defer){const annotator=$('annotator').value.trim(),status=defer?'uncertain':'labeled',severity=defer?'':selected('quality'),kind=defer?'':severity==='0'?'none':selected('kind'),note=$('note').value.trim();
 if(!annotator){$('message').textContent='Nhập tên của bạn ở phía trên trước nhé.';$('annotator').focus();return}
 if(!defer&&severity===''){$('message').textContent='Chọn 1 trong 3 mức chất lượng trước nhé.';return}
 if(!defer&&!kind){$('message').textContent='Chọn loại lỗi ở bước 2 trước nhé.';return}
 labels[current().image_id]={status,defect_type:kind,severity,status_saved_at:new Date().toISOString(),annotator,note};persist();
 if(index<pool().length-1){index++;show();$('message').textContent=defer?'Đã để ảnh trước lại để xem sau.':'Đã lưu ảnh trước. Tiếp tục với ảnh này nhé.'}else{show();$('message').textContent='Đã lưu ảnh cuối của phần này. Kiểm tra ảnh chưa làm / để xem lại, rồi tải kết quả.'}}
$('save').onclick=()=>save(false);$('defer').onclick=()=>save(true);
$('prev').onclick=()=>{index--;show()};$('next').onclick=()=>{index++;show()};$('split').onchange=()=>{index=0;show()};
$('unlabeled').onclick=()=>{const at=pool().findIndex(x=>!labels[x.image_id]);if(at<0){$('message').textContent='Split này không còn ảnh chưa gán.';return}index=at;show()};
$('revisit').onclick=()=>{const at=pool().findIndex(x=>labels[x.image_id]?.status==='uncertain');if(at<0){$('message').textContent='Phần này không có ảnh để xem lại.';return}index=at;show()};
$('photo').onclick=()=>{const w=window.open('','_blank');if(w){const img=w.document.createElement('img');img.src=current().image;img.alt=current().image_id;w.document.body.append(img)}};
function download(name,content,type){const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
$('backup').onclick=()=>download('t02_manual_labels_backup.json',JSON.stringify({dataset,policy,labels,annotator:$('annotator').value},null,2),'application/json');
$('restore').onchange=async e=>{try{const s=JSON.parse(await e.target.files[0].text());if(s.dataset!==dataset||s.policy!==policy||!s.labels||typeof s.labels!=='object')throw Error('Bản sao khác dataset/quy tắc.');
 const allowed=new Set(items.map(x=>x.image_id));for(const [id,v] of Object.entries(s.labels)){if(!allowed.has(id)||!v||!['labeled','uncertain'].includes(v.status))throw Error('Nhãn không hợp lệ.');
 if(v.status==='labeled'&&(!['none','blur','glare','dark','compression'].includes(v.defect_type)||!['0','1','2'].includes(v.severity)||(v.defect_type==='none')!==(v.severity==='0')))throw Error('Loại lỗi/severity không hợp lệ.');
 if(!v.annotator||!v.status_saved_at)throw Error('Thiếu thông tin nhãn.')}
 if(!confirm('Thay thế nhãn hiện tại bằng bản sao? Hãy tải backup hiện tại trước nếu cần.'))return;
 labels=s.labels;$('annotator').value=s.annotator||'';persist();show();alert('Đã khôi phục.')}catch(err){alert('Không khôi phục được: '+err.message)}finally{e.target.value=''}};
const cell=v=>'"'+String(v??'').replaceAll('"','""')+'"';
$('export').onclick=()=>{const fields=['image_id','split','camera_id','light','defect_type','severity','is_defect','status','annotator','labeled_at','note','policy_version','image_sha256'];
 const rows=items.map(x=>{const v=labels[x.image_id]||{};return[x.image_id,x.split,x.camera_id,x.light,v.defect_type,v.severity,v.status==='labeled'?(v.severity==='2'?1:0):'',v.status||'unlabeled',v.annotator,v.status_saved_at,v.note,policy,x.sha256].map(cell).join(',')});
 download('t02_manual_labels.csv','\uFEFF'+[fields.join(','),...rows].join('\r\n'),'text/csv;charset=utf-8')};
show();
</script></html>'''


def main() -> None:
    source = FIXTURE / "images.csv"
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        raw = (FIXTURE / row["path"]).read_bytes()
        row["sha256"] = hashlib.sha256(raw).hexdigest()
        row["image"] = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
    digest = hashlib.sha256(source.read_bytes() + "".join(r["sha256"] for r in rows).encode()).hexdigest()
    page = PAGE.replace("__ITEMS__", json.dumps(rows, ensure_ascii=True)).replace("__HASH__", json.dumps(digest))
    output = ROOT / "out/labeling/t02_manual_labeling.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    print(f"Created {output} ({len(rows)} images; all initial labels blank)")


if __name__ == "__main__":
    main()
