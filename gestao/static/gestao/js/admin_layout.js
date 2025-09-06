document.addEventListener('DOMContentLoaded', function () {
  const btn = document.getElementById('sidebarToggle');
  if (!btn) return;
  btn.addEventListener('click', function () {
    document.body.classList.toggle('sidebar-collapsed');
  });
});