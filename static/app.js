const $ = id => document.getElementById(id);
async function post(url, body) {
  const r = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || 'Something went wrong. Try again.');
  return d;
}
function md(t) {
  const e = t.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  return e.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/^\* /gm, '• ');
}
