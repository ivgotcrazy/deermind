// 本文件只演示已确认交互，不连接模型、不计算掌握状态。
const root = document.getElementById('deermind-directions');
const student = root.querySelector('.dm-student');
const admin = root.querySelector('.dm-admin');
const messages = root.querySelector('.dm-messages');
const chat = root.querySelector('.dm-material-chat');
const grid = root.querySelector('.dm-student-grid');
const state = document.getElementById('sample-state');
let view = location.hash === '#admin' ? 'admin' : 'student';
let pending = null;
let pendingButton = null;
let roundOpen = false;

function showView(next) {
  stop();
  view = next;
  student.hidden = next !== 'student';
  admin.hidden = next !== 'admin';
  root.querySelectorAll('[data-view]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === next)));
  location.hash = next;
  state.value = 'normal';
}
function add(text, user = false) {
  const node = document.createElement('div');
  node.className = user ? 'dm-user-message' : 'sample-status';
  node.textContent = text;
  if (view === 'student') { messages.append(node); node.scrollIntoView({block:'nearest'}); }
  else chat.insertBefore(node, chat.querySelector('.dm-composer'));
  return node;
}
function stop() {
  if (pending !== null) clearTimeout(pending);
  pending = null;
  if (pendingButton) { pendingButton.textContent = '发送'; pendingButton.setAttribute('aria-label','发送'); pendingButton = null; }
  root.querySelectorAll('[data-processing]').forEach(n => n.remove());
}
function process(button, callback) {
  pendingButton = button;
  button.textContent = '停止本次回复';
  button.setAttribute('aria-label','停止本次回复');
  const wait = add('正在整理回复…');
  wait.dataset.processing = 'true';
  pending = setTimeout(() => { stop(); callback(); }, 1200);
}
root.querySelectorAll('[data-view]').forEach(b => b.onclick = () => showView(b.dataset.view));
window.addEventListener('hashchange', () => { const next=location.hash==='#admin'?'admin':'student'; if(next!==view) showView(next); });
showView(view);

const bookButton = root.querySelector('.dm-book-toggle');
bookButton.onclick = () => {
  const hidden = grid.classList.toggle('dm-book-hidden');
  bookButton.querySelector('span').textContent = hidden ? '展开教材' : '收起教材';
  bookButton.setAttribute('aria-expanded',String(!hidden));
};
document.getElementById('directory-toggle').onclick = event => {
  const hidden = grid.classList.toggle('no-directory');
  event.currentTarget.textContent = hidden ? '展开目录' : '收起目录';
};
document.getElementById('chat-toggle').onclick = event => {
  const hidden = grid.classList.toggle('no-chat');
  event.currentTarget.textContent = hidden ? '展开聊天' : '收起聊天';
};
root.querySelectorAll('.dm-history-item').forEach((item,index) => {
  const label=item.querySelector('span');
  const button=document.createElement('button');
  button.textContent=label.textContent;
  label.replaceWith(button);
  const entry=document.createElement('div');
  entry.className='sample-history-entry';
  entry.textContent=index===0?'09:12 自由交谈已结束：今天想学分数。':'昨天16:30 讲解已结束：生活中的分数。';
  messages.prepend(entry);
  button.onclick=()=>entry.scrollIntoView({block:'start'});
});
const child=root.querySelector('.dm-current-activity');
const locate=document.createElement('button');locate.textContent='定位这段答疑';child.append(locate);
locate.onclick=()=>root.querySelector('.dm-flow-marker')?.scrollIntoView({block:'start'});

function plan() {
  if(pendingButton) return;
  if (roundOpen) return add('请先提交本轮答案，或结束本轮后再开始新的检测。');
  const card=add('检测准备好了：1道新题，检查“增加四分之一”的独立求解。确认后才开始。');
  const start=document.createElement('button');start.textContent='开始检测';card.append(document.createElement('br'),start);
  start.onclick=()=> {
    start.disabled=true;roundOpen=true;
    root.querySelector('.dm-path').textContent='讲解 ／ 检测';
    root.querySelector('.dm-chat-heading h2').textContent='增加四分之一 · 独立检测';
    add('进入检测 · 第1轮');
    const task=document.createElement('section');task.className='round-card';
    task.innerHTML='<h3>第1题</h3><p>图书角原来有60本书，增加了原来的四分之一，现在有多少本？写出算式，并说说你的想法。</p><label>我的答案<textarea aria-label="我的答案"></textarea></label><button type="button" data-submit>提交答案</button><button type="button" data-help>给我一点提示</button>';
    messages.append(task);task.scrollIntoView({block:'nearest'});
    task.querySelector('[data-submit]').onclick=()=> {
      if(!task.querySelector('textarea').value.trim()) {task.querySelector('textarea').focus();return;}
      closeRound(task);add('本轮已提交（mock）。样例解法：60 ÷ 4 = 15，60 ＋ 15 = 75。正式系统根据实际作答反馈，本样板不更新掌握状态。');
    };
    task.querySelector('[data-help]').onclick=()=> {
      closeRound(task);add('独立检测轮已结束。进入答疑：先想一想，原来60本书的四分之一是多少？');
      root.querySelector('.dm-path').textContent='讲解 ／ 检测 ／ 答疑';
      root.querySelector('.dm-chat-heading h2').textContent='怎样求增加的部分？';
    };
  };
}
function closeRound(task) {roundOpen=false;task.querySelectorAll('textarea,button').forEach(e=>e.disabled=true);add('检测轮结束');}
document.getElementById('request-detection').onclick=plan;
document.getElementById('return-explanation').onclick=()=> {
  if(pendingButton) return;
  if(roundOpen) return add('请先提交本轮答案，或请求提示以结束独立检测轮。');
  root.querySelector('.dm-path').textContent='讲解';
  root.querySelector('.dm-chat-heading h2').textContent='理解增加四分之一';
  add('答疑结束，回到讲解：新增的20人要加回原来的80人。');
};
messages.scrollTop=messages.scrollHeight;
root.querySelectorAll('.dm-composer').forEach(composer => {
  const input=composer.querySelector('textarea');
  const button=composer.querySelector('button');
  button.onclick=()=> {
    if(pendingButton===button) {stop();add('已停止本次回复，未发送的草稿仍保留。');return;}
    if(pendingButton || !input.value.trim()) return;
    const value=input.value.trim();input.value='';add(value,true);
    process(button,()=> {
      if(view==='admin') {
        add('已生成新的核对候选（mock）。请对照右侧题目与解法；采用后才更新教材解析内容。');
        root.querySelector('.dm-status').textContent='待采用';
        root.querySelector('.dm-candidate-footer button').disabled=false;
      } else if(roundOpen) add('当前是独立检测，请在答题区提交；需要帮助时点击“给我一点提示”，先结束本轮。');
      else if(/检测|测验/.test(value)) plan();
      else add('这是一条预置回复，用来评审中文阅读和追问体验：先确定“原来的人数”是整体，再求它的四分之一，最后加回原量。');
    });
  };
});
root.querySelector('.dm-candidate-footer button').onclick=event=> {
  root.querySelector('.dm-status').textContent='已采用';event.currentTarget.disabled=true;
  add('候选已采用（mock）。解析内容已更新，领域入库和章节关联仍分别处理。');
};
state.onchange=()=> {
  stop();
  const target=view==='student'?messages:chat;
  target.querySelectorAll('.sample-status').forEach(n=>n.remove());
  [...target.children].forEach(n=>n.hidden=false);
  if(state.value==='normal') return;
  if(state.value==='empty'&&view==='student') [...messages.children].forEach(n=>n.hidden=true);
  const text={empty:'还没有交流记录。可以直接提问，也可以先浏览教材。',busy:'正在处理上一条消息。新输入保留为草稿。',error:'本次处理未完成，草稿和已有内容仍保留。'}[state.value];
  const notice=add(text);
  if(state.value==='busy') {notice.dataset.processing='true';pendingButton=target.closest('.dm-window').querySelector('.dm-composer button');pendingButton.textContent='停止本次回复';pendingButton.setAttribute('aria-label','停止本次回复');}
  if(state.value==='error') {
    const retry=document.createElement('button');retry.textContent='重试';notice.append(document.createElement('br'),retry);
    retry.onclick=()=>{notice.remove();state.value='normal';add('已恢复（mock）。可以继续交流，之前的草稿没有丢失。');};
  }
};
