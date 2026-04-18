/* ============================================================
   NCfly Design System — icons.js
   Shared icon sprite (lucide-style, 24x24 viewBox).
   Usage: <svg class="icon"><use href="#icon-users"/></svg>
   Include the SVG sprite once per page (see _partials.html).
   ============================================================ */
window.NC_ICONS = `
<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">
<defs>
  <symbol id="icon-home" viewBox="0 0 24 24"><path d="M3 11l9-8 9 8"/><path d="M5 9v12h14V9"/></symbol>
  <symbol id="icon-users" viewBox="0 0 24 24"><path d="M17 20v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2"/><circle cx="10" cy="7" r="4"/><path d="M21 20v-2a4 4 0 0 0-3-3.9"/><path d="M17 3.1A4 4 0 0 1 17 11"/></symbol>
  <symbol id="icon-plane" viewBox="0 0 24 24"><path d="M10.2 13.8 2 11l20-8-8 20-2.8-8.2-5.4-2.8 4.4-3.2z"/></symbol>
  <symbol id="icon-ticket" viewBox="0 0 24 24"><path d="M3 9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4z"/><path d="M12 7v10" stroke-dasharray="2 2"/></symbol>
  <symbol id="icon-wallet" viewBox="0 0 24 24"><path d="M3 6a2 2 0 0 1 2-2h11l4 4v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M16 14h.01"/><path d="M3 10h18"/></symbol>
  <symbol id="icon-piggy" viewBox="0 0 24 24"><path d="M2 10v4h2a8 8 0 0 0 2.5 3.5V20h3v-1.5A8 8 0 0 0 12 19a8 8 0 0 0 2.5-.5V20h3v-2.5A8 8 0 0 0 20 14h2v-4h-2a8 8 0 0 0-8-6 8 8 0 0 0-8 6z"/><circle cx="16" cy="11" r="1"/></symbol>
  <symbol id="icon-chart" viewBox="0 0 24 24"><path d="M3 3v18h18"/><path d="M7 14l4-4 4 4 5-5"/></symbol>
  <symbol id="icon-building" viewBox="0 0 24 24"><path d="M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16"/><path d="M10 21v-4"/><path d="M16 11h4a2 2 0 0 1 2 2v8"/><path d="M7 8h2M7 12h2M13 8h2M13 12h2M18 15h2M18 18h2"/></symbol>
  <symbol id="icon-hotel" viewBox="0 0 24 24"><path d="M3 21V8l9-5 9 5v13"/><path d="M9 12v9M15 12v9M3 16h18"/></symbol>
  <symbol id="icon-refresh" viewBox="0 0 24 24"><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/></symbol>
  <symbol id="icon-settings" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></symbol>
  <symbol id="icon-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></symbol>
  <symbol id="icon-bell" viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></symbol>
  <symbol id="icon-sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></symbol>
  <symbol id="icon-moon" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></symbol>
  <symbol id="icon-plus" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></symbol>
  <symbol id="icon-eye" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></symbol>
  <symbol id="icon-edit" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4z"/></symbol>
  <symbol id="icon-trash" viewBox="0 0 24 24"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/></symbol>
  <symbol id="icon-more" viewBox="0 0 24 24"><circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/></symbol>
  <symbol id="icon-filter" viewBox="0 0 24 24"><path d="M22 3H2l8 9.5V19l4 2v-8.5z"/></symbol>
  <symbol id="icon-download" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5M12 15V3"/></symbol>
  <symbol id="icon-arrow-right" viewBox="0 0 24 24"><path d="M5 12h14M13 5l7 7-7 7"/></symbol>
  <symbol id="icon-arrow-left" viewBox="0 0 24 24"><path d="M19 12H5M11 5l-7 7 7 7"/></symbol>
  <symbol id="icon-check" viewBox="0 0 24 24"><path d="M5 12l5 5L20 7"/></symbol>
  <symbol id="icon-check-circle" viewBox="0 0 24 24"><path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="M22 4L12 14.01l-3-3"/></symbol>
  <symbol id="icon-x" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l18 12" stroke="currentColor"/><path d="M6 6l12 12"/></symbol>
  <symbol id="icon-chevron-down" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></symbol>
  <symbol id="icon-chevron-right" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></symbol>
  <symbol id="icon-logout" viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/></symbol>
  <symbol id="icon-alert" viewBox="0 0 24 24"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></symbol>
  <symbol id="icon-help" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></symbol>
  <symbol id="icon-trend-up" viewBox="0 0 24 24"><path d="M22 7l-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/></symbol>
  <symbol id="icon-trend-down" viewBox="0 0 24 24"><path d="M22 17l-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/></symbol>
  <symbol id="icon-swap" viewBox="0 0 24 24"><path d="M17 1l4 4-4 4"/><path d="M3 11v-2a4 4 0 0 1 4-4h14"/><path d="M7 23l-4-4 4-4"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></symbol>
  <symbol id="icon-credit-card" viewBox="0 0 24 24"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/></symbol>
  <symbol id="icon-menu" viewBox="0 0 24 24"><path d="M3 6h18M3 12h18M3 18h18"/></symbol>
  <symbol id="icon-user" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></symbol>
  <symbol id="icon-calc" viewBox="0 0 24 24"><rect x="4" y="2" width="16" height="20" rx="2"/><path d="M8 6h8M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01"/></symbol>
  <symbol id="icon-bed" viewBox="0 0 24 24"><path d="M2 20V9M2 13h20M22 20v-7a3 3 0 0 0-3-3h-9v6"/><circle cx="6" cy="14" r="2"/></symbol>
  <symbol id="icon-vault" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="12" r="4"/><path d="M12 8v.5M12 15.5v.5M15.5 12H16M8 12h.5"/></symbol>
  <symbol id="icon-badge" viewBox="0 0 24 24"><circle cx="12" cy="8" r="6"/><path d="M15.5 13l2 9-5.5-3-5.5 3 2-9"/></symbol>
  <symbol id="icon-pin" viewBox="0 0 24 24"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></symbol>
  <symbol id="icon-plane-tail" viewBox="0 0 24 24"><path d="M14.6 16H21l-3-9-3 3-6-1 3-5-3-1-4 6-3-1 1 5 3 3 2-1 4 2z"/></symbol>
  <symbol id="icon-shield" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-4"/></symbol>
  <symbol id="icon-book" viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5v14z"/><path d="M4 19.5V22h16"/></symbol>
  <symbol id="icon-chat" viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></symbol>
  <symbol id="icon-shuffle" viewBox="0 0 24 24"><path d="M16 3h5v5M4 20l17-17M21 16v5h-5M15 15l6 6M4 4l5 5"/></symbol>
  <symbol id="icon-file" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M9 13h6M9 17h6"/></symbol>
  <symbol id="icon-copy" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></symbol>
  <symbol id="icon-link" viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></symbol>
</defs>
</svg>
`;
document.addEventListener('DOMContentLoaded', () => {
  if (!document.getElementById('nc-icon-sprite')) {
    const d = document.createElement('div');
    d.id = 'nc-icon-sprite';
    d.innerHTML = window.NC_ICONS;
    document.body.prepend(d);
  }
});
