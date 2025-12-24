// ============================================
// SIDEBAR MOBILE - JavaScript Melhorado
// ============================================

document.addEventListener('DOMContentLoaded', function() {
  const sidebar = document.querySelector('.sidebar');
  const menuToggles = Array.from(document.querySelectorAll('[data-sidebar-toggle]'));
  
  // Fechar sidebar ao clicar em um link
  if (sidebar && menuToggles.length) {
    menuToggles.forEach(menuToggle => {
      menuToggle.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        sidebar.classList.toggle('active');
        const isOpen = sidebar.classList.contains('active');
        menuToggles.forEach(toggle => toggle.setAttribute('aria-expanded', isOpen));
      });
    });
  }

  if (sidebar) {
    const sidebarLinks = sidebar.querySelectorAll('a');
    sidebarLinks.forEach(link => {
      link.addEventListener('click', function() {
        if (window.innerWidth <= 768) {
          sidebar.classList.remove('active');
          menuToggles.forEach(toggle => toggle.setAttribute('aria-expanded', 'false'));
        }
      });
    });
  }
  
  // Fechar sidebar ao clicar fora
  document.addEventListener('click', function(e) {
    if (sidebar && menuToggles.length && window.innerWidth <= 768) {
      const isClickInsideSidebar = sidebar.contains(e.target);
      const isClickOnToggle = menuToggles.some(toggle => toggle.contains(e.target));

      if (!isClickInsideSidebar && !isClickOnToggle && sidebar.classList.contains('active')) {
        sidebar.classList.remove('active');
        menuToggles.forEach(toggle => toggle.setAttribute('aria-expanded', 'false'));
      }
    }
  });
  
  // Atualizar ao redimensionar
  window.addEventListener('resize', function() {
    if (sidebar && menuToggles.length) {
      if (window.innerWidth > 768) {
        sidebar.classList.remove('active');
        menuToggles.forEach(toggle => toggle.setAttribute('aria-expanded', 'false'));
      }
    }
  });
});
