// Tweaks panel: primary color, radius, density, dark mode
// Provides: window.NC_TWEAKS.init(options)
(function () {
  const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
    "primary": "#3182ce",
    "primaryDark": "#2c5282",
    "radius": 12,
    "density": "compact",
    "dark": false
  }/*EDITMODE-END*/;

  function apply(tweaks) {
    const r = document.documentElement;
    r.style.setProperty('--primary', tweaks.primary);
    r.style.setProperty('--primary-dark', tweaks.primaryDark);
    // Derive primary-50 lighter
    r.style.setProperty('--primary-50', mix(tweaks.primary, '#ffffff', 0.88));
    r.style.setProperty('--primary-100', mix(tweaks.primary, '#ffffff', 0.75));
    r.style.setProperty('--r-md', tweaks.radius + 'px');
    r.style.setProperty('--r-sm', Math.max(4, tweaks.radius - 4) + 'px');
    r.style.setProperty('--r-lg', (tweaks.radius + 4) + 'px');
    r.setAttribute('data-density', tweaks.density);
    r.setAttribute('data-theme', tweaks.dark ? 'dark' : 'light');
  }

  function mix(a, b, t) {
    const ah = a.replace('#', ''), bh = b.replace('#', '');
    const ar = parseInt(ah.substr(0, 2), 16), ag = parseInt(ah.substr(2, 2), 16), ab = parseInt(ah.substr(4, 2), 16);
    const br = parseInt(bh.substr(0, 2), 16), bg = parseInt(bh.substr(2, 2), 16), bb = parseInt(bh.substr(4, 2), 16);
    const rr = Math.round(ar + (br - ar) * t);
    const rg = Math.round(ag + (bg - ag) * t);
    const rb = Math.round(ab + (bb - ab) * t);
    return '#' + [rr, rg, rb].map(n => n.toString(16).padStart(2, '0')).join('');
  }

  let state = { ...TWEAK_DEFAULTS };
  try { const s = localStorage.getItem('nc_tweaks'); if (s) state = { ...state, ...JSON.parse(s) }; } catch (e) { }
  apply(state);

  function panel() {
    const el = document.createElement('div');
    el.id = 'nc-tweaks';
    el.innerHTML = `
      <div class="nct-card">
        <div class="nct-head">
          <b>Tweaks</b>
          <button class="nct-close" aria-label="Fechar">×</button>
        </div>
        <label>Cor primária
          <div class="nct-colors">
            ${['#3182ce','#2563eb','#7c3aed','#0ea5e9','#059669','#d97706','#dc2626','#1a365d'].map(c =>
              `<button data-color="${c}" style="background:${c}" aria-label="${c}"></button>`).join('')}
          </div>
        </label>
        <label>Raio das bordas
          <input type="range" min="4" max="20" step="1" data-k="radius" value="${state.radius}">
          <small>${state.radius}px</small>
        </label>
        <label>Densidade
          <div class="nct-seg" data-k="density">
            <button data-v="compact">Compacta</button>
            <button data-v="comfortable">Confortável</button>
          </div>
        </label>
        <label class="nct-row">
          <span>Dark mode</span>
          <input type="checkbox" data-k="dark" ${state.dark ? 'checked' : ''}>
        </label>
      </div>
    `;
    document.body.appendChild(el);
    if (!document.getElementById('nc-tweaks-style')) {
      const s = document.createElement('style');
      s.id = 'nc-tweaks-style';
      s.textContent = `
        #nc-tweaks-toggle { position:fixed; right:20px; bottom:20px; z-index:1001;
          background:var(--ink-strong); color:#fff; border:0; padding:10px 14px;
          border-radius:999px; font-weight:600; font-size:13px; box-shadow:var(--sh-lg);
          display:flex; align-items:center; gap:8px; cursor:pointer; font-family:var(--ff); }
        #nc-tweaks-toggle:hover { background:#000; }
        #nc-tweaks { position:fixed; right:20px; bottom:76px; z-index:1000; width:280px;
          background:var(--surface); border:1px solid var(--border); border-radius:14px;
          box-shadow:var(--sh-lg); padding:14px 16px; font-family:var(--ff);
          transform: translateY(8px); opacity:0; pointer-events:none; transition:all .2s; }
        #nc-tweaks.is-open { transform: translateY(0); opacity:1; pointer-events:auto; }
        #nc-tweaks label { display:block; font-size:12px; font-weight:700; color:var(--muted);
          text-transform:uppercase; letter-spacing:.08em; margin:12px 0 6px; }
        #nc-tweaks .nct-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; border-bottom:1px solid var(--divider); padding-bottom:8px;}
        #nc-tweaks .nct-head b { color:var(--ink); text-transform:none; letter-spacing:0; font-size:14px; }
        #nc-tweaks .nct-close { background:none; border:0; font-size:20px; color:var(--subtle); cursor:pointer; }
        #nc-tweaks .nct-colors { display:grid; grid-template-columns:repeat(8,1fr); gap:4px; }
        #nc-tweaks .nct-colors button { width:100%; aspect-ratio:1; border:2px solid transparent; border-radius:6px; cursor:pointer; }
        #nc-tweaks .nct-colors button.is-on { border-color: var(--ink); }
        #nc-tweaks input[type="range"] { width:100%; accent-color: var(--primary); }
        #nc-tweaks .nct-seg { display:grid; grid-template-columns:1fr 1fr; gap:4px; background:var(--surface-2); padding:3px; border-radius:8px; }
        #nc-tweaks .nct-seg button { border:0; background:transparent; padding:6px 10px; border-radius:6px;
          font-size:12px; font-weight:600; color:var(--muted); cursor:pointer; }
        #nc-tweaks .nct-seg button.is-on { background:var(--surface); color:var(--ink); box-shadow:var(--sh-sm); }
        #nc-tweaks .nct-row { display:flex; justify-content:space-between; align-items:center; text-transform:none; letter-spacing:0; font-size:13px; color:var(--ink); font-weight:500; }
        #nc-tweaks .nct-row input { width:40px; height:22px; accent-color: var(--primary); }
        #nc-tweaks small { color:var(--subtle); font-size:11px; }
      `;
      document.head.appendChild(s);
    }

    // Markers
    markSelected(el);

    el.addEventListener('click', (ev) => {
      const c = ev.target.dataset.color;
      if (c) {
        state.primary = c;
        state.primaryDark = shade(c, -15);
        apply(state); persist(); markSelected(el);
      }
      if (ev.target.closest('.nct-close')) document.getElementById('nc-tweaks-toggle').click();
      if (ev.target.matches('.nct-seg button')) {
        const k = ev.target.closest('.nct-seg').dataset.k;
        state[k] = ev.target.dataset.v; apply(state); persist(); markSelected(el);
      }
    });
    el.addEventListener('input', (ev) => {
      const k = ev.target.dataset.k;
      if (!k) return;
      if (ev.target.type === 'checkbox') state[k] = ev.target.checked;
      else if (ev.target.type === 'range') state[k] = parseInt(ev.target.value, 10);
      apply(state); persist();
      const s = ev.target.parentElement.querySelector('small');
      if (s && ev.target.type === 'range') s.textContent = ev.target.value + 'px';
    });
  }

  function markSelected(el) {
    el.querySelectorAll('.nct-colors button').forEach(b => b.classList.toggle('is-on', b.dataset.color === state.primary));
    el.querySelectorAll('.nct-seg button').forEach(b => b.classList.toggle('is-on', b.dataset.v === state.density));
  }

  function shade(hex, pct) {
    const n = parseInt(hex.replace('#', ''), 16);
    let r = (n >> 16) + pct * 2.55;
    let g = ((n >> 8) & 0xff) + pct * 2.55;
    let b = (n & 0xff) + pct * 2.55;
    r = Math.max(0, Math.min(255, r | 0));
    g = Math.max(0, Math.min(255, g | 0));
    b = Math.max(0, Math.min(255, b | 0));
    return '#' + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join('');
  }
  function persist() { try { localStorage.setItem('nc_tweaks', JSON.stringify(state)); } catch (e) { } }

  // Integration w/ host Tweaks button (works standalone too)
  function init() {
    // Add a floating toggle so it works even without host toolbar
    if (!document.getElementById('nc-tweaks-toggle')) {
      const b = document.createElement('button');
      b.id = 'nc-tweaks-toggle';
      b.innerHTML = '⚙ Tweaks';
      b.addEventListener('click', () => {
        const p = document.getElementById('nc-tweaks');
        if (!p) { panel(); requestAnimationFrame(() => document.getElementById('nc-tweaks').classList.add('is-open')); }
        else p.classList.toggle('is-open');
      });
      document.body.appendChild(b);
    }
    // Register with host
    window.addEventListener('message', (ev) => {
      if (ev.data?.type === '__activate_edit_mode') {
        if (!document.getElementById('nc-tweaks')) panel();
        document.getElementById('nc-tweaks').classList.add('is-open');
      } else if (ev.data?.type === '__deactivate_edit_mode') {
        document.getElementById('nc-tweaks')?.classList.remove('is-open');
      }
    });
    setTimeout(() => {
      try { window.parent.postMessage({ type: '__edit_mode_available' }, '*'); } catch (e) {}
    }, 50);
  }
  window.NC_TWEAKS = { init, apply, getState: () => state };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
