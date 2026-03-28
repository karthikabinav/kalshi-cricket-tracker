async function loadData() {
  const res = await fetch('./data/dashboard-data.json', { cache: 'no-store' });
  if (!res.ok) throw new Error(`Failed to load dashboard data: ${res.status}`);
  return res.json();
}

function formatUsd(value, { signed = false, compact = false } = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    notation: compact ? 'compact' : 'standard',
    signDisplay: signed ? 'always' : 'auto',
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(Number(value));
}

function formatDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString('en-US', {
    year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit',
    timeZone: 'UTC'
  }) + ' UTC';
}

function badge(label, tone) {
  return `<span class="badge ${tone}">${label}</span>`;
}

function renderKpis(summary) {
  const items = [
    {
      label: 'Realized PnL',
      value: formatUsd(summary.realizedPnlUsd, { signed: true }),
      footnote: `${summary.tradesWithRealizedPnl} trades with closed/known PnL`,
      className: summary.realizedPnlUsd > 0 ? 'pos' : summary.realizedPnlUsd < 0 ? 'neg' : ''
    },
    {
      label: 'Transaction volume',
      value: formatUsd(summary.totalTransactionVolumeUsd),
      footnote: `${summary.executedTradeCount} executed trades logged`,
      className: ''
    },
    {
      label: 'Open positions',
      value: formatNumber(summary.openTradeCount),
      footnote: `${summary.closedTradeCount} closed / resolved`,
      className: ''
    },
    {
      label: 'Last decision',
      value: summary.lastDecision?.decision || 'No decisions',
      footnote: summary.lastDecision ? `${summary.lastDecision.side} • confidence ${summary.lastDecision.confidence}` : 'No BTC15 decision logs yet',
      className: ''
    }
  ];

  document.getElementById('kpi-grid').innerHTML = items.map(item => `
    <article class="kpi-card">
      <div class="kpi-label">${item.label}</div>
      <div class="kpi-value ${item.className}">${item.value}</div>
      <div class="kpi-footnote">${item.footnote}</div>
    </article>
  `).join('');
}

function renderAssumptions(assumptions) {
  document.getElementById('assumptions').innerHTML = assumptions.map(text => `<li>${text}</li>`).join('');
}

function renderTrades(trades) {
  const body = document.getElementById('trades-body');
  if (!trades.length) {
    body.innerHTML = '<tr><td colspan="8" class="muted">No BTC15 executed trades found in artifacts.</td></tr>';
    return;
  }
  body.innerHTML = trades.map(trade => {
    const pnlClass = trade.pnlUsd > 0 ? 'pos' : trade.pnlUsd < 0 ? 'neg' : 'muted';
    const statusTone = trade.status === 'OPEN' ? 'amber' : 'blue';
    return `
      <tr>
        <td>${formatDate(trade.entryTime)}</td>
        <td>${trade.ticker || '—'}</td>
        <td>${badge(trade.side || '—', trade.side === 'YES' ? 'green' : trade.side === 'NO' ? 'red' : 'blue')}</td>
        <td>${badge(trade.status, statusTone)}</td>
        <td>${trade.limitPriceCents != null ? `${formatNumber(trade.limitPriceCents)}¢` : '—'}</td>
        <td>${formatNumber(trade.filledSize, 0)}</td>
        <td>${formatUsd(trade.volumeUsd)}</td>
        <td class="${pnlClass}">${formatUsd(trade.pnlUsd, { signed: true })}</td>
      </tr>
    `;
  }).join('');
}

function renderDecisions(decisions) {
  const container = document.getElementById('decision-list');
  if (!decisions.length) {
    container.innerHTML = '<div class="empty">No BTC15 decision rows found.</div>';
    return;
  }
  container.innerHTML = decisions.map(item => {
    const tone = item.decision === 'TRADE' ? 'green' : 'amber';
    return `
      <div class="decision-item">
        <div class="decision-top">
          <div>${badge(item.decision, tone)}</div>
          <div class="decision-meta">${formatDate(item.loggedAt)}</div>
        </div>
        <div class="decision-meta">${item.ticker || '—'} • ${item.side || 'NONE'} • confidence ${item.confidence ?? '—'}</div>
        <div class="decision-reason">${item.reason || 'No reason logged.'}</div>
      </div>
    `;
  }).join('');
}

function renderChart(points) {
  const root = document.getElementById('pnl-chart');
  if (!points.length) {
    root.innerHTML = '<div class="empty">No realized PnL series available yet.</div>';
    return;
  }

  const width = 900;
  const height = 280;
  const padding = { top: 16, right: 20, bottom: 34, left: 56 };
  const xs = points.map((_, idx) => idx);
  const ys = points.map(p => Number(p.cumulativePnlUsd) || 0);
  const minY = Math.min(0, ...ys);
  const maxY = Math.max(0, ...ys);
  const ySpan = maxY - minY || 1;
  const xMax = Math.max(1, xs.length - 1);
  const xScale = i => padding.left + (i / xMax) * (width - padding.left - padding.right);
  const yScale = y => padding.top + ((maxY - y) / ySpan) * (height - padding.top - padding.bottom);
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xScale(i).toFixed(2)} ${yScale(Number(p.cumulativePnlUsd) || 0).toFixed(2)}`).join(' ');
  const zeroY = yScale(0);
  const circles = points.map((p, i) => `<circle cx="${xScale(i)}" cy="${yScale(Number(p.cumulativePnlUsd) || 0)}" r="4" fill="#6ea8fe"><title>${formatDate(p.at)}: ${formatUsd(p.cumulativePnlUsd, { signed: true })}</title></circle>`).join('');
  const labels = [minY, 0, maxY].filter((v, i, arr) => arr.indexOf(v) === i).map(v => `
    <g>
      <line x1="${padding.left}" x2="${width - padding.right}" y1="${yScale(v)}" y2="${yScale(v)}" stroke="rgba(255,255,255,0.08)" />
      <text x="12" y="${yScale(v) + 4}" fill="#9da9c6" font-size="12">${formatUsd(v)}</text>
    </g>`).join('');

  root.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="PnL chart">
      ${labels}
      <line x1="${padding.left}" x2="${width - padding.right}" y1="${zeroY}" y2="${zeroY}" stroke="rgba(255,255,255,0.16)" stroke-dasharray="4 4" />
      <path d="${path}" fill="none" stroke="#6ea8fe" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
      ${circles}
    </svg>
  `;
}

function renderMeta(meta) {
  document.getElementById('data-source').textContent = meta.dataSource || 'artifacts snapshot';
  document.getElementById('generated-at').textContent = formatDate(meta.generatedAt);
}

loadData()
  .then((data) => {
    renderMeta(data.meta || {});
    renderKpis(data.summary || {});
    renderAssumptions(data.assumptions || []);
    renderTrades(data.trades || []);
    renderDecisions(data.decisions || []);
    renderChart(data.pnlSeries || []);
  })
  .catch((error) => {
    document.body.innerHTML = `<main class="page"><div class="panel"><h1>Dashboard load failed</h1><p class="subtext">${error.message}</p></div></main>`;
  });
