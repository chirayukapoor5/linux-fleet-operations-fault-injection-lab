// FleetOps API adapter. All authoritative state resides in SQLite via FastAPI.
const labApi = async (path, options = {}) => {
  const response = await fetch(path, {headers: {'Content-Type':'application/json'}, ...options});
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  return payload;
};
const showApiError = error => { console.error(error); alert(`FleetOps: ${error.message}`); };
async function refreshFleet() {
  try {
    const state = await labApi('/api/state');
    fleetNodes = state.nodes;
    incidents = state.incidents;
    alertLogs = state.logs.map(l => ({...l, time: new Date(l.time).toLocaleTimeString()}));
    renderFleetDashboard(); renderTickets(); populateNodeSelects();
    const stream = document.getElementById('alert-stream-box');
    stream.replaceChildren();
    for (const l of alertLogs) {
      const el = document.createElement('div');
      el.textContent = `[${l.time}] [${l.node}] [${l.level}] ${l.msg}`;
      el.className = l.level === 'ERROR' ? 'text-red-400' : l.level === 'WARN' ? 'text-amber-400' : 'text-cyan-400';
      stream.appendChild(el);
    }
    const count = document.querySelector('header .hidden.md\\:flex .text-cyan-400');
    if (count) count.textContent = `${fleetNodes.filter(n => n.status === 'HEALTHY').length} / ${fleetNodes.length}`;
  } catch (e) { showApiError(e); }
}
// The original HTML starts a timer invoking this function; it is intentionally disabled.
simulateTelemetryFluctuation = () => {};
executeModalFault = async function () {
  const node_id = document.getElementById('modal-node-select').value;
  const fault_type = document.getElementById('modal-fault-type').value;
  try {
    await labApi('/api/faults', {method:'POST', body:JSON.stringify({node_id, fault_type})});
    closeFaultModal(); await refreshFleet(); switchTab('dashboard');
  } catch(e) {showApiError(e);}
};
resetAllNodes = async function () {
  if (!confirm('Reset the entire training fleet and clear incident history?')) return;
  try {await labApi('/api/reset', {method:'POST'}); await refreshFleet();} catch(e) {showApiError(e);}
};
resolveCurrentTicket = async function () {
  try {await labApi(`/api/incidents/${encodeURIComponent(selectedTicketId)}/resolve`, {method:'POST'}); closeTicketModal(); await refreshFleet();} catch(e) {showApiError(e);}
};
processTerminalCommand = async function (command) {
  try {
    const result = await labApi('/api/diagnostics', {method:'POST', body:JSON.stringify({node_id:currentTerminalNode, command})});
    appendTerminalOutput(`[SIMULATED DIAGNOSTIC]\n${result.output}`, 'text-emerald-400');
  } catch(e) { appendTerminalOutput(`ERROR: ${e.message}`, 'text-red-400'); }
};
runHealthCheckScript = async function () {
  try {
    const report = await labApi('/api/health-check');
    document.getElementById('script-output-container').classList.remove('hidden');
    const output = document.getElementById('script-terminal-output');
    output.replaceChildren();
    const pre = document.createElement('pre');
    pre.textContent = JSON.stringify(report, null, 2);
    output.appendChild(pre);
  } catch(e) {showApiError(e);}
};
copyScriptCode = async function () {
  const snippet = document.querySelector('#tab-health pre code').textContent;
  try {await navigator.clipboard.writeText(snippet); alert('Copied display-only example. Live health checks are served by /api/health-check.');} catch(e) {showApiError(e);}
};
document.addEventListener('DOMContentLoaded', () => {
  // Wait until the original HTML initialization has finished.
  queueMicrotask(refreshFleet);
  setInterval(refreshFleet, 5000);
  const heading = document.querySelector('#tab-terminal h2');
  if (heading) heading.textContent = 'Read-Only Diagnostic Terminal Simulator';
  document.querySelector('#tab-terminal p').textContent = 'Allowlisted diagnostic emulation only. No SSH connection or host commands are executed.';
  const description = document.querySelector('#tab-dashboard p');
  if (description) description.textContent = 'Isolated training fleet with API-backed state, incident history, and Prometheus metrics.';
});
