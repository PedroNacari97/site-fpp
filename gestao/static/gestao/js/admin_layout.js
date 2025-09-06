const btn = document.getElementById('sidebarToggle');
if (btn) {
  btn.addEventListener('click', () => {
    document.body.classList.toggle('sidebar-collapsed');
  });
}