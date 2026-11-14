import {renderDocument, esc} from './render.js';

const cases = ['C02', 'C03', 'C05', 'C06'];
const names = {statement:'题面', reference:'教材解法', teaching_aid:'教学辅助', derived_view:'结构数据表'};
let current, role = 'statement';

function renderRole() {
  const roles = Object.keys(names).filter(r => current.documents.some(d => d.role === r));
  if (!roles.includes(role)) role = 'statement';
  document.querySelector('#tabs').innerHTML = roles.map(r => `<button data-role-tab="${r}" class="${r === role ? 'active' : ''}">${names[r]}${r === 'reference' ? '（'+current.documents.filter(d => d.role === r).length+'）' : ''}</button>`).join('');
  document.querySelectorAll('[data-role-tab]').forEach(button => button.addEventListener('click', () => {role = button.dataset.roleTab; renderRole();}));
  const note = role === 'derived_view' ? '<div class="notice">以下是同一批图中数据生成的表格视图，原书此处没有这张表。切回题面不会展示它。</div>' : role === 'reference' ? '<div class="notice">教材已有解法，独立于题面；约分标记保留原数及替换过程。</div>' : role === 'teaching_aid' ? '<div class="notice">教材旁注单独保存，不混入检测题面。</div>' : '';
  document.querySelector('#rendered').innerHTML = note + current.documents.filter(d => d.role === role).map(d => renderDocument(d, current)).join('');
  document.body.dataset.role = role;
}

async function load() {
  const cid = cases.includes(location.hash.slice(1)) ? location.hash.slice(1) : 'C02';
  document.body.dataset.loaded = '';
  const [dataResponse, checkResponse] = await Promise.all([fetch(`cases/${cid}.json`), fetch('checks.json')]);
  if (!dataResponse.ok || !checkResponse.ok) throw new Error('结构稿或检查结果加载失败');
  current = await dataResponse.json();
  const checks = await checkResponse.json();
  role = 'statement';
  document.querySelectorAll('nav a').forEach(a => a.classList.toggle('active', a.hash === '#'+cid));
  document.querySelector('#overview').innerHTML = `<h2>${cid} · ${esc(current.title)}</h2><span class="badge">结构与约束检查通过 · 尚未进行本轮 Agent 提取</span>`;
  document.querySelector('#sources').innerHTML = current.sources.map(s => `<div class="source"><a href="${esc(s.file)}" target="_blank" rel="noopener"><img src="${esc(s.file)}" alt="教材第${s.page}页既定来源区域"></a><p>印刷页 ${s.page} · 裁剪区域 ${s.pixel_box.join(', ')} · <a href="${esc(s.original_file)}" target="_blank" rel="noopener">查看原整页</a></p></div>`).join('');
  document.querySelector('#notes').innerHTML = current.notes.map(n => `<li>${esc(n)}</li>`).join('');
  document.querySelector('#checks').textContent = `4例校验通过；${checks.negative_cases.length}个反例被拦截。完整性检查使用作者对照原图建立的固定清单，不能证明未知材料不会漏提。`;
  document.querySelector('#json').textContent = JSON.stringify(current, null, 2);
  renderRole();
  document.body.dataset.loaded = cid;
}

function fail(error) {document.querySelector('#rendered').innerHTML = `<p class="error">${esc(error.message)}</p>`; console.error(error);}
window.addEventListener('hashchange', () => load().catch(fail));
load().catch(fail);
