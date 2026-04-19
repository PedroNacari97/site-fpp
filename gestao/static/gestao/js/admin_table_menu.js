/*
 * admin_table_menu.js
 * Menu kebab reutilizavel (.admin-table-menu) para linhas de tabelas do admin.
 * Vanilla JS, sem dependencias. Listeners delegados no document.
 *
 * Requisitos de markup:
 *   <div class="admin-table-menu" data-row-menu>
 *     <button class="admin-table-menu__trigger" aria-haspopup="menu" aria-expanded="false">...</button>
 *     <div class="admin-table-menu__popover" role="menu" hidden>
 *       <a|button role="menuitem" class="admin-table-menu__item">...</a|button>
 *       ...
 *     </div>
 *   </div>
 *
 * Acessibilidade:
 *  - Abre/fecha com clique no trigger
 *  - Esc fecha e devolve foco ao trigger
 *  - Clique fora fecha
 *  - Selecionar item fecha (antes de navegar/acionar)
 *  - Tab/Shift+Tab navegam normalmente entre itens
 *  - Somente um menu aberto por vez
 *  - data-confirm-delete em itens continua funcionando via delegacao existente
 */
(function () {
  'use strict';

  var OPEN_CLASS = 'admin-table-menu--open';
  var GAP = 6; // espacamento vertical entre trigger e popover

  function getMenu(trigger) {
    var wrapper = trigger.closest('.admin-table-menu');
    if (!wrapper) return null;
    return wrapper.querySelector('.admin-table-menu__popover');
  }

  /*
   * Posiciona o popover (position: fixed) ancorado ao trigger usando
   * getBoundingClientRect. Alinha a borda direita do popover com a
   * borda direita do trigger por padrao; se estourar a esquerda ou
   * direita do viewport, reposiciona para caber. Se nao houver espaco
   * abaixo, abre para cima.
   */
  function positionPopover(wrapper) {
    var trigger = wrapper.querySelector('.admin-table-menu__trigger');
    var popover = wrapper.querySelector('.admin-table-menu__popover');
    if (!trigger || !popover) return;

    var triggerRect = trigger.getBoundingClientRect();
    // popover precisa estar visivel para medir; ja foi setado hidden=false em openMenu
    var popRect = popover.getBoundingClientRect();
    var popW = popRect.width || popover.offsetWidth || 200;
    var popH = popRect.height || popover.offsetHeight || 0;

    var vw = document.documentElement.clientWidth;
    var vh = document.documentElement.clientHeight;
    var margin = 8;

    // horizontal: alinhar borda direita do popover com borda direita do trigger
    var left = triggerRect.right - popW;
    if (left < margin) left = margin;
    if (left + popW > vw - margin) left = vw - margin - popW;
    if (left < margin) left = margin; // fallback viewport muito estreito

    // vertical: abrir para baixo se couber, senao para cima
    var top = triggerRect.bottom + GAP;
    if (top + popH > vh - margin && triggerRect.top - GAP - popH >= margin) {
      top = triggerRect.top - GAP - popH;
    }
    if (top < margin) top = margin;

    popover.style.left = Math.round(left) + 'px';
    popover.style.top = Math.round(top) + 'px';
  }

  function closeMenu(wrapper, opts) {
    if (!wrapper) return;
    var trigger = wrapper.querySelector('.admin-table-menu__trigger');
    var popover = wrapper.querySelector('.admin-table-menu__popover');
    if (!trigger || !popover) return;
    wrapper.classList.remove(OPEN_CLASS);
    trigger.setAttribute('aria-expanded', 'false');
    popover.hidden = true;
    if (opts && opts.focusTrigger) {
      trigger.focus();
    }
  }

  function closeAll(except, opts) {
    var menus = document.querySelectorAll('.admin-table-menu.' + OPEN_CLASS);
    for (var i = 0; i < menus.length; i++) {
      if (menus[i] !== except) {
        closeMenu(menus[i], opts);
      }
    }
  }

  function openMenu(wrapper) {
    var trigger = wrapper.querySelector('.admin-table-menu__trigger');
    var popover = wrapper.querySelector('.admin-table-menu__popover');
    if (!trigger || !popover) return;
    closeAll(wrapper);
    wrapper.classList.add(OPEN_CLASS);
    trigger.setAttribute('aria-expanded', 'true');
    popover.hidden = false;
    positionPopover(wrapper);
  }

  // Click no trigger: alterna
  document.addEventListener('click', function (e) {
    var trigger = e.target.closest('.admin-table-menu__trigger');
    if (trigger) {
      e.preventDefault();
      e.stopPropagation();
      var wrapper = trigger.closest('.admin-table-menu');
      if (!wrapper) return;
      var isOpen = wrapper.classList.contains(OPEN_CLASS);
      if (isOpen) {
        closeMenu(wrapper);
      } else {
        openMenu(wrapper);
      }
      return;
    }

    // Click em item do menu: fecha antes de o clique se propagar
    var item = e.target.closest('.admin-table-menu__item');
    if (item) {
      var wrapperItem = item.closest('.admin-table-menu');
      if (wrapperItem) {
        closeMenu(wrapperItem);
      }
      // nao devolve foco ao trigger aqui: o usuario navegou por acao
      return;
    }

    // Click fora de qualquer menu: fecha todos
    if (!e.target.closest('.admin-table-menu')) {
      closeAll();
    }
  });

  // Esc fecha o menu aberto e devolve foco ao trigger
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var open = document.querySelector('.admin-table-menu.' + OPEN_CLASS);
    if (!open) return;
    e.stopPropagation();
    closeMenu(open, { focusTrigger: true });
  });

  // Tab fora do menu fecha (mantem navegacao natural por teclado)
  document.addEventListener('focusin', function (e) {
    var open = document.querySelector('.admin-table-menu.' + OPEN_CLASS);
    if (!open) return;
    if (!open.contains(e.target)) {
      closeMenu(open);
    }
  });

  /*
   * Qualquer scroll (pagina, wrapper da tabela com overflow-x:auto,
   * containers internos) ou resize desancora o popover (ele usa
   * position: fixed em coordenadas de viewport). Fechar e' mais
   * simples e previsivel do que reposicionar.
   * Capturing: true para pegar scroll de elementos filhos que nao
   * borbulham scroll no bubbling phase.
   */
  document.addEventListener('scroll', function () {
    closeAll();
  }, true);

  window.addEventListener('resize', function () {
    closeAll();
  });
})();
