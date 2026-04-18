// Shared admin sidebar + topbar. Usage:
//   <div data-shell="admin" data-active="clientes" data-title="Clientes" data-subtitle="Gerenciar cadastro"></div>
// Then NCflyShell.render();
window.NCflyShell = (function(){
  const ADMIN_NAV = [
    {section:'Principal'},
    {id:'dashboard', href:'admin-dashboard.html', icon:'home', label:'Dashboard'},
    {id:'clientes', href:'admin-clientes.html', icon:'users', label:'Clientes'},
    {id:'empresas', href:'admin-empresas.html', icon:'building', label:'Empresas'},
    {section:'Operações'},
    {id:'cotacoes', href:'admin-cotacoes.html', icon:'calc', label:'Cotações'},
    {id:'cotar', href:'cotar-emitir.html', icon:'plane', label:'Cotar & emitir'},
    {id:'emissoes', href:'admin-emissoes.html', icon:'ticket', label:'Emissões'},
    {id:'hoteis', href:'admin-hoteis.html', icon:'bed', label:'Hotéis'},
    {section:'Pontos'},
    {id:'contas', href:'admin-contas.html', icon:'wallet', label:'Contas fidelidade'},
    {id:'contas-adm', href:'admin-contas-administradas.html', icon:'vault', label:'Contas administradas'},
    {id:'programas', href:'admin-programas.html', icon:'badge', label:'Programas'},
    {id:'movimentacoes', href:'admin-movimentacoes.html', icon:'swap', label:'Movimentações'},
    {id:'transferencia', href:'transferencia-adm.html', icon:'shuffle', label:'Transferências'},
    {section:'Cadastros'},
    {id:'aeroportos', href:'admin-aeroportos.html', icon:'pin', label:'Aeroportos'},
    {id:'companhias', href:'admin-companhias.html', icon:'plane-tail', label:'Companhias aéreas'},
    {id:'auditoria', href:'admin-auditoria.html', icon:'shield', label:'Auditoria'},
  ];
  const CLIENT_NAV = [
    {section:'Minha conta'},
    {id:'painel', href:'painel-cliente.html', icon:'home', label:'Meu painel'},
    {id:'programas', href:'cliente-programas.html', icon:'wallet', label:'Meus programas'},
    {id:'emissoes', href:'cliente-emissoes.html', icon:'ticket', label:'Minhas emissões'},
    {id:'hoteis', href:'cliente-hoteis.html', icon:'bed', label:'Hotéis'},
    {id:'movimentacoes', href:'cliente-movimentacoes.html', icon:'swap', label:'Movimentações'},
    {section:'Ajuda'},
    {id:'ajuda', href:'#', icon:'book', label:'Como funciona'},
    {id:'contato', href:'#', icon:'chat', label:'Falar com gestor'},
  ];

  function renderNav(navItems, active){
    return navItems.map(it => {
      if(it.section) return `<div class="sidebar__section">${it.section}</div>`;
      const isActive = it.id===active ? 'is-active' : '';
      return `<a class="nav-item ${isActive}" href="${it.href}">
        <svg class="icon"><use href="#icon-${it.icon}"/></svg>
        <span>${it.label}</span>
      </a>`;
    }).join('');
  }

  function render(){
    const root = document.querySelector('[data-shell]');
    if(!root) return;
    const kind = root.dataset.shell; // 'admin' or 'client'
    const active = root.dataset.active || '';
    const title = root.dataset.title || '';
    const subtitle = root.dataset.subtitle || '';
    const breadcrumb = root.dataset.breadcrumb || '';
    const user = kind==='client' ? {name:'Maria Silva', role:'Cliente', initials:'MS', color:'linear-gradient(135deg,#f59e0b,#dc2626)'} : {name:'Pedro Nacari', role:'Administrador', initials:'PN', color:'linear-gradient(135deg,var(--primary),var(--accent))'};
    const nav = kind==='client' ? CLIENT_NAV : ADMIN_NAV;
    const actions = root.dataset.actions || '';
    const showSearch = root.dataset.search !== 'false';

    root.outerHTML = `
      <div class="app">
        <aside class="sidebar">
          <div class="sidebar__brand"><img src="../assets/ncfly-logo.svg" alt="NCfly"></div>
          ${renderNav(nav, active)}
          <div class="sidebar__foot">
            <div class="sidebar__user" style="background:${user.color}">${user.initials}</div>
            <div class="meta"><b>${user.name}</b><small>${user.role}</small></div>
          </div>
        </aside>
        <main>
          <header class="topbar">
            ${showSearch ? `<div class="topbar__search"><svg class="icon"><use href="#icon-search"/></svg><input class="input" placeholder="Buscar…"></div>` : ''}
            ${breadcrumb ? `<div style="color:var(--muted);font-size:13px">${breadcrumb}</div>` : ''}
            <div class="spacer"></div>
            ${actions}
            <button class="btn btn--icon btn--ghost" title="Notificações"><svg class="icon"><use href="#icon-bell"/></svg></button>
          </header>
          <div class="page" id="page-root">
            ${title ? `<div class="page__head"><div><h1>${title}</h1>${subtitle?`<p>${subtitle}</p>`:''}</div></div>` : ''}
            <div id="page-body"></div>
          </div>
        </main>
      </div>`;
  }
  return {render};
})();
