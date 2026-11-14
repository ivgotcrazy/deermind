// Four-case review renderer. No model-generated markup is executed.
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels = {multiply:'×', divide:'÷', add:'+', subtract:'−', equal:'='};
const priorities = {equal:1, add:2, subtract:2, multiply:3, divide:3, fraction:9, number:9, symbol:9, group:9};

function expression(node, parentPriority = 0, right = false) {
  const priority = priorities[node.op];
  if (priority === undefined) throw new Error('未支持的公式节点：' + node.op);
  let html;
  if (node.op === 'number') {
    const steps = [node.value, ...(node.cancel_to || [])];
    html = `<mn class="${steps.length > 1 ? 'cancelled' : ''}">${esc(steps[0])}</mn>`;
    for (let i = 1; i < steps.length; i++) {
      html = `<mover data-cancellation><mrow>${html}</mrow><mn class="${i < steps.length - 1 ? 'cancelled' : ''}">${esc(steps[i])}</mn></mover>`;
    }
  } else if (node.op === 'symbol') html = `<mi>${esc(node.name)}</mi>`;
  else if (node.op === 'fraction') html = `<mfrac>${expression(node.args[0])}${expression(node.args[1])}</mfrac>`;
  else if (node.op === 'group') html = `<mrow><mo>(</mo>${expression(node.args[0])}<mo>)</mo></mrow>`;
  else html = `<mrow>${expression(node.args[0], priority)}<mo>${labels[node.op]}</mo>${expression(node.args[1], priority, true)}</mrow>`;
  if (priority < parentPriority || (right && priority === parentPriority && priority < 9)) {
    html = `<mrow><mo>(</mo>${html}<mo>)</mo></mrow>`;
  }
  return html;
}

const math = node => `<math xmlns="http://www.w3.org/1998/Math/MathML">${expression(node)}</math>`;
const text = (x, y, value, attrs = '') => `<text x="${x}" y="${y}" ${attrs}>${esc(value)}</text>`;
const svg = (body, title, width = 660, height = 330) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(title)}"><title>${esc(title)}</title>${body}</svg>`;

function inline(items) {
  return items.map(item => {
    if (item.type === 'text') return esc(item.text);
    if (item.type === 'math') return math(item.expression);
    if (item.type === 'response_blank') return `<span class="response-blank" data-blank aria-label="${esc(item.label)}"></span>`;
    throw new Error('未支持的行内类型：' + item.type);
  }).join('');
}

function scalar(cell) {
  if (cell.state !== 'provided' || cell.content.length !== 1 || cell.content[0].type !== 'text') {
    throw new Error('图表有未确定数据，不能按零绘制');
  }
  return cell.content[0].text;
}

function tableView(table, caption) {
  const states = {response_blank:'待填写', source_missing:'原文未提供', unreadable:'识别不清'};
  return `<div class="table-scroll"><table><caption>${esc(caption)}</caption><thead><tr>${table.columns.map(c => `<th>${esc(c.label)}${c.unit ? ' / ' + esc(c.unit) : ''}</th>`).join('')}</tr></thead><tbody>${table.rows.map(row => `<tr>${row.map(cell => `<td>${cell.state === 'provided' ? inline(cell.content) : `<span class="unknown">${states[cell.state]}</span>`}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

function chart(b, table) {
  const index = key => table.columns.findIndex(c => c.key === key);
  const categories = table.rows.map(row => scalar(row[index(b.category_column)]));
  const series = b.series.map(s => ({...s, labels: table.rows.map(row => scalar(row[index(s.column)]))}));
  if (b.kind === 'pie') {
    let angle = -Math.PI / 2, body = '';
    const cx = 175, cy = 160, radius = 110;
    series[0].labels.forEach((label, i) => {
      const value = Number(label), next = angle + value / 100 * 2 * Math.PI;
      const x1 = cx + radius * Math.cos(angle), y1 = cy + radius * Math.sin(angle);
      const x2 = cx + radius * Math.cos(next), y2 = cy + radius * Math.sin(next);
      body += `<path d="M${cx} ${cy} L${x1} ${y1} A${radius} ${radius} 0 ${value > 50 ? 1 : 0} 1 ${x2} ${y2} Z" fill="${esc(b.slice_colors[i])}" stroke="white" stroke-width="2"/>`;
      body += `<rect x="345" y="${60+i*55}" width="14" height="14" fill="${esc(b.slice_colors[i])}"/>`;
      body += text(370, 73+i*55, `${categories[i]}：${label}%`);
      angle = next;
    });
    return svg(body, b.title);
  }
  const axis = b.axis, left = 62, right = 620, bottom = 240, top = 30;
  const y = value => bottom - (value - axis.min) / (axis.max - axis.min) * (bottom - top);
  let body = text(12, 18, axis.label);
  for (let tick = axis.min; tick <= axis.max + 1e-8; tick += axis.step) {
    body += `<line x1="${left}" y1="${y(tick)}" x2="${right}" y2="${y(tick)}" stroke="#d8e1e5"/>`;
    body += text(left-12, y(tick)+5, tick ? tick.toFixed(1) : '0', 'text-anchor="end"');
  }
  const groupWidth = (right-left) / categories.length;
  categories.forEach((label, i) => {body += text(left+groupWidth*(i+.5), bottom+27, label, 'text-anchor="middle"');});
  series.forEach((s, j) => {
    const points = s.labels.map((value, i) => [left+groupWidth*(i+.5), y(Number(value))]);
    if (b.kind === 'line') body += `<polyline points="${points.map(p => p.join(',')).join(' ')}" fill="none" stroke="${esc(s.color)}" stroke-width="3"/>`;
    points.forEach(([x, py], i) => {
      const bx = x+(j-(series.length-1)/2)*42;
      if (b.kind === 'bar') body += `<rect x="${bx-16}" y="${py}" width="32" height="${bottom-py}" fill="${esc(s.color)}"/>`;
      else body += `<circle cx="${x}" cy="${py}" r="4" fill="${esc(s.color)}"/>`;
      body += text(b.kind === 'bar' ? bx : x, py+(b.kind === 'line' && j ? 23 : -10), s.labels[i], 'text-anchor="middle"');
    });
    body += `<rect x="${145+j*225}" y="298" width="14" height="14" fill="${esc(s.color)}"/>` + text(166+j*225, 311, s.label);
  });
  return svg(body, b.title);
}

function diagram(b) {
  let body = '';
  for (const o of b.objects) {
    const [x, y, width, height] = o.layout_box, cx = x+width/2, cy = y+height/2;
    const attrs = 'fill="none" stroke="#157e9d" stroke-width="2"';
    let shape;
    if (o.shape === 'circle') shape = `<circle cx="${cx}" cy="${cy}" r="${width/2}" ${attrs}/>`;
    else if (o.shape === 'ellipse') shape = `<ellipse cx="${cx}" cy="${cy}" rx="${width/2}" ry="${height/2}" ${attrs}/>`;
    else if (o.shape === 'square') shape = `<rect data-square x="${x}" y="${y}" width="${width}" height="${height}" ${attrs}/>`;
    else if (o.shape === 'triangle') shape = `<polygon points="${cx},${y} ${x+width},${y+height} ${x},${y+height}" ${attrs}/>`;
    else {
      const count = {triangle:3, pentagon:5, hexagon:6}[o.shape];
      const points = Array.from({length:count}, (_, i) => {const a = (o.shape === 'hexagon' ? 0 : -Math.PI/2)+2*Math.PI*i/count; return `${cx+width/2*Math.cos(a)},${cy+height/2*Math.sin(a)}`;}).join(' ');
      shape = `<polygon points="${points}" ${attrs}/>`;
    }
    body += `<g data-shape="${esc(o.shape)}">${shape}<circle data-mark cx="${o.mark.position[0]}" cy="${o.mark.position[1]}" r="2.8" fill="#c03e76"/></g>`;
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${b.view_box.join(' ')}" role="img" aria-label="${esc(b.title)}"><title>${esc(b.title)}</title>${body}</svg>`;
}

export function renderDocument(doc, data) {
  const tables = new Map(data.data_tables.map(t => [t.id, t]));
  return `<section class="document" data-role="${doc.role}"><h2>${esc(doc.title)}</h2>${doc.blocks.map(b => {
    let html;
    if (b.type === 'paragraph') html = `<p>${inline(b.content)}</p>`;
    else if (b.type === 'math_sequence') html = `<div class="math-sequence" data-purpose="${b.purpose}">${b.lines.map(line => `<div class="math-line"><span class="relation">${esc(line.relation)}</span>${math(line.expression)}${esc(line.suffix)}</div>`).join('')}</div>`;
    else if (b.type === 'chart') html = `<figure data-chart="${b.kind}"><figcaption>${esc(b.title)}</figcaption>${chart(b, tables.get(b.data_ref))}</figure>`;
    else if (b.type === 'table') html = tableView(tables.get(b.data_ref), b.caption);
    else if (b.type === 'diagram') html = diagram(b);
    else throw new Error('未支持的内容块：' + b.type);
    return `<div class="content-block" data-block="${esc(b.id)}">${html}</div>`;
  }).join('')}</section>`;
}

export {esc};
