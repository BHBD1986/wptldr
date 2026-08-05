const state = { topic: 'agtech', from: '2026-01-01', to: '', q: '', page: 1 };
const today = new Date().toISOString().slice(0, 10);
document.getElementById('date-from').value = state.from;
document.getElementById('date-to').value = today;

async function api(path, opts) {
  const r = await fetch(path, opts || {});
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function loadStats() {
  const s = await api('/api/stats');
  document.getElementById('stats').textContent =
    `${s.articles} articles · ${s.summarized} summarized · ${s.date_min} to ${s.date_max}`;
}

function closeDrilldown() {
  const el = document.getElementById('drilldown-card');
  if (el) el.remove();
}

async function loadTopics() {
  const bar = document.getElementById('topic-bar');
  const topics = await api('/api/topics');
  bar.innerHTML = topics.map(t =>
    `<button class="pill${t.topic === state.topic ? ' active' : ''}" data-topic="${t.topic}">
      ${t.topic} <span class="cnt">${t.count}</span>
    </button>`
  ).join('');
  bar.querySelectorAll('[data-topic]').forEach(btn =>
    btn.addEventListener('click', () => {
      state.topic = btn.dataset.topic;
      state.page = 1;
      closeDrilldown();
      loadTopics();
      loadArticles();
    })
  );
}

async function loadArticles() {
  closeDrilldown();
  const el = document.getElementById('article-list');
  const params = new URLSearchParams({
    topic: state.topic,
    from: state.from,
    to: state.to || today,
    page: state.page,
    page_size: 20
  });
  if (state.q) params.set('q', state.q);
  const data = await api(`/api/articles?${params}`);
  el.innerHTML = data.items.map(a => `
    <div class="card" data-id="${a.id}">
      <h3>${esc(a.title)}</h3>
      <div class="meta">
        <span class="section">${esc(a.section)}</span>
        ${a.published_at.slice(0, 10)}
      </div>
      <div class="${a.tldr ? 'tldr' : 'pending'}">${a.tldr ? esc(a.tldr) : 'Summary pending…'}</div>
      <div class="topics">${a.topics.map(t => `<span>${t}</span>`).join('')}</div>
    </div>
  `).join('');

  el.querySelectorAll('.card').forEach(c =>
    c.addEventListener('click', () => openDrilldown(+c.dataset.id))
  );

  const pages = data.pages;
  document.getElementById('pager').innerHTML = `
    <button ${state.page <= 1 ? 'disabled' : ''} data-page="${state.page - 1}">Prev</button>
    <span>Page ${state.page} of ${pages}</span>
    <button ${state.page >= pages ? 'disabled' : ''} data-page="${state.page + 1}">Next</button>
  `;
  document.querySelectorAll('#pager button[data-page]').forEach(b =>
    b.addEventListener('click', () => {
      state.page = +b.dataset.page;
      loadArticles();
    })
  );
}

async function openDrilldown(id) {
  closeDrilldown();
  const card = document.querySelector(`.card[data-id="${id}"]`);
  if (!card) return;

  const a = await api(`/api/articles/${id}`);
  const html = `
    <div class="drilldown-card" id="drilldown-card">
      <h2>${esc(a.title)}</h2>
      <div class="meta">
        <span class="section">${esc(a.section)}</span>
        ${a.published_at.slice(0, 10)}
      </div>
      <h3>TL;DR</h3>
      <div class="dd-tldr">${esc(a.tldr || 'No summary yet')}</div>
      <h3>Why It Matters</h3>
      <div class="dd-why">${esc(a.why_it_matters || '—')}</div>
      <h3>Key Points</h3>
      <ul class="dd-points">${a.key_points.map(p => `<li>${esc(p)}</li>`).join('')}</ul>
      <button class="dd-expand-btn" data-id="${id}">Go Deeper</button>
      <div class="dd-extra" id="dd-extra-${id}"></div>
      <h3>Related Articles</h3>
      <div class="dd-related">${a.related.map(r =>
        `<div class="dd-related-card" data-id="${r.id}"><strong>${esc(r.title)}</strong><br>${esc(r.tldr || '—')}</div>`
      ).join('')}</div>
      <a class="dd-source" href="${esc(a.url)}" target="_blank">Read full article →</a>
    </div>`;

  card.insertAdjacentHTML('afterend', html);
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  document.querySelector('.dd-expand-btn')?.addEventListener('click', async btn => {
    const el = btn.currentTarget;
    el.disabled = true;
    el.textContent = 'Loading…';
    const extra = document.getElementById(`dd-extra-${id}`);
    try {
      const res = await fetch(`/api/articles/${id}/expand`, { method: 'POST' });
      if (!res.ok) throw new Error('503');
      const data = await res.json();
      const c = data.content;
      extra.innerHTML = `
        <h4>Deeper Context</h4><p>${esc(c.deeper_context || '')}</p>
        <h4>Key Actors</h4><p>${esc((c.key_actors || []).join(', '))}</p>
        <h4>Outlook</h4><p>${esc(c.outlook || '')}</p>`;
      extra.classList.add('show');
      el.textContent = data.cached ? 'Go Deeper (cached)' : 'Done';
    } catch {
      el.textContent = 'Backend unavailable';
      setTimeout(() => { el.disabled = false; el.textContent = 'Retry'; }, 3000);
    }
  });

  document.querySelectorAll('.dd-related-card').forEach(c =>
    c.addEventListener('click', () => openDrilldown(+c.dataset.id))
  );
}

document.getElementById('date-from').addEventListener('change', e => {
  state.from = e.target.value; state.page = 1; loadArticles();
});
document.getElementById('date-to').addEventListener('change', e => {
  state.to = e.target.value; state.page = 1; loadArticles();
});
let debounce;
document.getElementById('q').addEventListener('input', e => {
  clearTimeout(debounce);
  debounce = setTimeout(() => { state.q = e.target.value; state.page = 1; loadArticles(); }, 300);
});

async function fetchCachedDigest(topic, from, to) {
  const params = new URLSearchParams({ topic, from, to });
  return api(`/api/digest?${params}`);
}

function renderDigest(data) {
  const d = data.digest;
  const body = document.getElementById('dg-body');
  const status = document.getElementById('dg-status');
  status.textContent = `${data.item_count} articles · ${data.cached ? 'cached' : 'fresh'}`;
  body.innerHTML = `
    <div class="dg-period">${esc(d.period_summary)}</div>
    <h3>Themes</h3>
    ${(d.themes || []).map(t => `<div class="dg-theme"><strong>${esc(t.theme)}</strong> ${esc(t.description)}</div>`).join('')}
    <h3>Key Stories</h3>
    ${(d.key_stories || []).map(s => `<div class="dg-story" data-id="${s.article_id || ''}"><strong>${esc(s.title)}</strong><br>${esc(s.why)}</div>`).join('')}
    <h3>Context</h3>
    <div class="dg-context">${esc(d.context || '')}</div>
    <h3>Outlook</h3>
    <div class="dg-outlook">${esc(d.outlook || '')}</div>`;
  body.querySelectorAll('.dg-story').forEach(el => {
    if (el.dataset.id) el.addEventListener('click', () => { document.getElementById('digest-modal').hidden = true; openDrilldown(+el.dataset.id); });
  });
}

function digestStageLabel(s) {
  if (s.stage === 'generating') return `Analyzing ${s.item_count || '…'} articles — this can take a minute or two on the local model`;
  if (s.stage === 'fetching') return 'Fetching articles…';
  if (s.stage === 'cached') return 'Loaded from cache';
  if (s.stage === 'failed') return s.error || 'Failed';
  if (s.stage === 'done') return 'Done';
  return 'Working…';
}

async function runDigest(force) {
  const modal = document.getElementById('digest-modal');
  const body = document.getElementById('dg-body');
  const status = document.getElementById('dg-status');
  const prog = document.getElementById('dg-progress');
  const fill = document.getElementById('dg-progress-fill');
  const label = document.getElementById('dg-progress-label');
  const regen = document.getElementById('dg-regenerate');
  modal.hidden = false;
  status.textContent = 'Starting…';
  body.innerHTML = '';
  regen.hidden = true;
  prog.hidden = false;
  fill.style.width = '0%';
  const params = new URLSearchParams({ topic: state.topic, from: state.from, to: state.to || today });
  if (force) params.set('force', 'true');
  try {
    await api(`/api/digest?${params}`, { method: 'POST' });
    const started = Date.now();
    const poll = setInterval(async () => {
      const s = await api('/api/digest/status');
      const pct = Math.max(0, Math.min(100, s.pct || 0));
      fill.style.width = pct + '%';
      const elapsed = Math.round((Date.now() - started) / 1000);
      label.textContent = `${digestStageLabel(s)} · ${pct}% (${elapsed}s)`;
      if (!s.running) {
        clearInterval(poll);
        if (s.stage === 'failed') {
          fill.style.width = '100%';
          fill.classList.add('fail');
          status.textContent = 'Topic Brief failed';
          body.innerHTML = `
            <div class="dg-hint">
              <strong>Too much content?</strong> The brief couldn't be completed for this many articles.
              Try narrowing the <strong>date range</strong> (e.g. to a single month), or use the
              <strong>search box</strong> to focus on fewer articles, then run Topic Brief again.
            </div>
            <div class="dg-err">${esc(s.error || 'Unknown error')}</div>`;
          regen.hidden = false;
          return;
        }
        try {
          const data = await fetchCachedDigest(state.topic, state.from, state.to || today);
          prog.hidden = true;
          renderDigest(data);
          regen.hidden = false;
        } catch {
          status.textContent = 'Failed to load brief';
          regen.hidden = false;
        }
      }
    }, 1000);
  } catch {
    status.textContent = 'Failed to start';
    prog.hidden = true;
    regen.hidden = false;
  }
}

document.getElementById('brief-btn').addEventListener('click', () => runDigest(false));

document.getElementById('digest-modal').querySelector('.modal-close').addEventListener('click', () => {
  document.getElementById('digest-modal').hidden = true;
});

document.getElementById('dg-regenerate').addEventListener('click', () => runDigest(true));

document.getElementById('update-btn').addEventListener('click', async () => {
  const btn = document.getElementById('update-btn');
  const status = document.getElementById('update-status');
  btn.disabled = true;
  status.textContent = `Starting (${state.topic})…`;
  try {
    await api(`/api/update?topic=${encodeURIComponent(state.topic)}`, { method: 'POST' });
    const poll = setInterval(async () => {
      const s = await api('/api/update/status');
      const stage = (s.stage || '…').replace('summarization:', 'summarizing ');
      status.textContent = s.running
        ? `Updating ${s.topic || state.topic}: ${stage}`
        : s.result === 'completed' ? 'Done' : `Failed: ${s.error}`;
      if (!s.running) {
        clearInterval(poll);
        btn.disabled = false;
        if (s.result === 'completed') {
          loadStats();
          loadTopics();
          loadArticles();
        }
      }
    }, 2000);
  } catch {
    status.textContent = 'Failed to start';
    btn.disabled = false;
  }
});

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

loadStats();
loadTopics();
loadArticles();
