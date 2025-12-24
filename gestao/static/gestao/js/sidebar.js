document.addEventListener("DOMContentLoaded", () => {
    const sidebar = document.querySelector("[data-sidebar]");
    const overlay = document.querySelector("[data-sidebar-overlay]");
    const toggleButtons = document.querySelectorAll("[data-sidebar-toggle]");

    if (!sidebar || toggleButtons.length === 0) return;

    toggleButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            // Desktop: colapsa sidebar
            if (window.innerWidth >= 768) {
                sidebar.classList.toggle("collapsed");
            } 
            // Mobile: abre/fecha sidebar
            else {
                document.body.classList.toggle("sidebar-open");
            }
        });
    });

    // Fecha sidebar mobile ao clicar no overlay
    if (overlay) {
        overlay.addEventListener("click", () => {
            document.body.classList.remove("sidebar-open");
        });
    }

    const handleResize = () => {
        if (window.innerWidth >= 768) {
            document.body.classList.remove("sidebar-open");
        }
    };

    window.addEventListener("resize", handleResize);
    handleResize();
});
