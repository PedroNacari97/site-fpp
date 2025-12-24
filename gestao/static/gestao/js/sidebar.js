// ============================================
// SIDEBAR MOBILE - JavaScript Melhorado
// ============================================

document.addEventListener('DOMContentLoaded', function() {
  const sidebar = document.querySelector('.sidebar');
  
  // Encontrar ou criar botão de toggle
  let menuToggle = document.querySelector('[data-sidebar-toggle]');
  
  if (!menuToggle) {
    const header = document.querySelector('header') || document.querySelector('.header');
    if (header) {
      menuToggle = document.createElement('button');
      menuToggle.className = 'menu-toggle';
      menuToggle.setAttribute('data-sidebar-toggle', '');
      menuToggle.innerHTML = '☰';
      menuToggle.style.cssText = `
        background: transparent;
        color: white;
        border: none;
        padding: 8px 12px;
        cursor: pointer;
        font-size: 20px;
        font-weight: 600;
        display: none;
        z-index: 1001;
      `;
      header.insertBefore(menuToggle, header.firstChild);
    }
  }
  
  // Adicionar evento ao botão
  if (menuToggle && sidebar) {
    menuToggle.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      sidebar.classList.toggle('active');
      menuToggle.setAttribute('aria-expanded', sidebar.classList.contains('active'));
    });
  }
  
  // Fechar sidebar ao clicar em um link
  if (sidebar) {
    const sidebarLinks = sidebar.querySelectorAll('a');
    sidebarLinks.forEach(link => {
      link.addEventListener('click', function() {
        if (window.innerWidth <= 768) {
          sidebar.classList.remove('active');
          if (menuToggle) {
            menuToggle.setAttribute('aria-expanded', 'false');
          }
        }
      });
    });
  }
  
  // Fechar sidebar ao clicar fora
  document.addEventListener('click', function(e) {
    if (sidebar && menuToggle && window.innerWidth <= 768) {
      const isClickInsideSidebar = sidebar.contains(e.target);
      const isClickOnToggle = menuToggle.contains(e.target);
      
      if (!isClickInsideSidebar && !isClickOnToggle && sidebar.classList.contains('active')) {
        sidebar.classList.remove('active');
        menuToggle.setAttribute('aria-expanded', 'false');
      }
    }
  });
  
  // Atualizar ao redimensionar
  window.addEventListener('resize', function() {
    if (sidebar && menuToggle) {
      if (window.innerWidth > 768) {
        sidebar.classList.remove('active');
        menuToggle.style.display = 'none';
      } else {
        menuToggle.style.display = 'block';
      }
    }
  });
  
  // Inicializar
  if (menuToggle && sidebar) {
    if (window.innerWidth <= 768) {
      menuToggle.style.display = 'block';
    } else {
      menuToggle.style.display = 'none';
    }
  }
});