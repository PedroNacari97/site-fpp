document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  const cookieName = body.dataset.cookieConsentName || "ncfly_cookie_preferences";
  const cookieVersion = body.dataset.cookieConsentVersion || "2026-04";
  const cookieMaxAgeDays = Number.parseInt(body.dataset.cookieConsentMaxAge || "180", 10);
  const metricsEndpoint = body.dataset.publicMetricsEndpoint || "";

  const banner = document.querySelector("[data-cookie-banner]");
  const modal = document.querySelector("[data-cookie-modal]");
  const analyticsAvailable =
    typeof window !== "undefined" &&
    typeof window.gtag === "function" &&
    Boolean(window.NCFlyAnalytics?.measurementId);

  const getCookieValue = (name) => {
    const prefix = `${name}=`;
    const match = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith(prefix));
    return match ? decodeURIComponent(match.slice(prefix.length)) : "";
  };

  const readPreferences = () => {
    const rawValue = getCookieValue(cookieName);
    if (!rawValue) {
      return null;
    }

    try {
      const parsed = JSON.parse(rawValue);
      if (parsed.version !== cookieVersion) {
        return null;
      }
      return {
        essential: true,
        analytics: Boolean(parsed.analytics),
      };
    } catch {
      return null;
    }
  };

  const writePreferences = (preferences) => {
    const payload = JSON.stringify({
      version: cookieVersion,
      essential: true,
      analytics: Boolean(preferences.analytics),
      updated_at: new Date().toISOString(),
    });
    const maxAge = Math.max(cookieMaxAgeDays, 30) * 24 * 60 * 60;
    document.cookie = `${cookieName}=${encodeURIComponent(payload)}; path=/; max-age=${maxAge}; SameSite=Lax`;
  };

  const currentPreferences = () => readPreferences() || { essential: true, analytics: true };

  const syncCookieInputs = () => {
    const preferences = currentPreferences();
    document.querySelectorAll("[data-cookie-setting='analytics']").forEach((input) => {
      input.checked = preferences.analytics;
    });
  };

  const openModal = () => {
    if (!modal) {
      return;
    }
    syncCookieInputs();
    modal.classList.remove("is-hidden");
    modal.setAttribute("aria-hidden", "false");
  };

  const closeModal = () => {
    if (!modal) {
      return;
    }
    modal.classList.add("is-hidden");
    modal.setAttribute("aria-hidden", "true");
  };

  const hideBanner = () => {
    if (banner) {
      banner.classList.add("is-hidden");
    }
  };

  const persistAndRefresh = (preferences) => {
    writePreferences(preferences);
    hideBanner();
    closeModal();
    window.location.reload();
  };

  document.querySelectorAll("[data-cookie-open-preferences]").forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      openModal();
    });
  });

  document.querySelectorAll("[data-cookie-close]").forEach((trigger) => {
    trigger.addEventListener("click", closeModal);
  });

  document.querySelectorAll("[data-cookie-action]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const action = trigger.getAttribute("data-cookie-action");

      if (action === "manage") {
        openModal();
        return;
      }

      if (action === "accept") {
        persistAndRefresh({ essential: true, analytics: true });
        return;
      }

      if (action === "reject") {
        persistAndRefresh({ essential: true, analytics: false });
        return;
      }

      if (action === "save") {
        const analyticsInput = document.querySelector("[data-cookie-setting='analytics']");
        persistAndRefresh({
          essential: true,
          analytics: Boolean(analyticsInput?.checked),
        });
      }
    });
  });

  // Ler mais no artigo (mobile)
  document.querySelectorAll("[data-article-readmore]").forEach((btn) => {
    const section = btn.closest("[data-article-content]");
    if (!section) return;
    btn.addEventListener("click", () => {
      section.setAttribute("data-expanded", "");
    });
  });

  // Dropdown de categorias no header
  document.querySelectorAll("[data-topbar-dropdown]").forEach((dropdown) => {
    const toggle = dropdown.querySelector("[data-dropdown-toggle]");
    if (!toggle) return;

    const open = () => {
      dropdown.classList.add("is-open");
      toggle.setAttribute("aria-expanded", "true");
    };
    const close = () => {
      dropdown.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    };

    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      dropdown.classList.contains("is-open") ? close() : open();
    });

    document.addEventListener("click", (e) => {
      if (!dropdown.contains(e.target)) close();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });
  });

  document.querySelectorAll("[data-topbar-search]").forEach((form) => {
    const toggle = form.querySelector("[data-search-toggle]");
    const input = form.querySelector("[data-search-input]");

    if (!toggle || !input) {
      return;
    }

    const setOpenState = (open) => {
      form.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    };

    const openSearch = () => {
      setOpenState(true);
      window.setTimeout(() => input.focus(), 10);
    };

    const closeSearch = () => {
      if (input.value.trim()) {
        return;
      }
      setOpenState(false);
    };

    if (input.value.trim()) {
      setOpenState(true);
    }

    toggle.addEventListener("click", (event) => {
      event.preventDefault();
      if (form.classList.contains("is-open") && !input.value.trim()) {
        closeSearch();
        return;
      }
      openSearch();
    });

    input.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeSearch();
        toggle.focus();
      }
    });

    document.addEventListener("click", (event) => {
      if (!form.contains(event.target)) {
        closeSearch();
      }
    });
  });

  const trackEvent = (name, params = {}) => {
    if (!analyticsAvailable) {
      return;
    }
    window.gtag("event", name, params);
  };

  const trackFirstPartyClick = (payload) => {
    if (!metricsEndpoint) {
      return;
    }

    const data = JSON.stringify(payload);

    try {
      if (navigator.sendBeacon) {
        const blob = new Blob([data], { type: "application/json" });
        navigator.sendBeacon(metricsEndpoint, blob);
        return;
      }
    } catch {}

    fetch(metricsEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: data,
      keepalive: true,
      credentials: "same-origin",
    }).catch(() => {});
  };

  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-analytics-event]");
    if (!target) {
      return;
    }

    trackEvent(target.dataset.analyticsEvent, {
      event_category: target.dataset.analyticsCategory || "engagement",
      event_label: target.dataset.analyticsLabel || "",
      destination_url: target.href || "",
      article_slug: target.dataset.analyticsSlug || "",
      article_category: target.dataset.analyticsArticleCategory || "",
      article_topic: target.dataset.analyticsArticleTopic || "",
      link_section: target.dataset.analyticsSection || "",
    });

    trackFirstPartyClick({
      event_name: target.dataset.analyticsEvent || "",
      path: window.location.pathname,
      section: target.dataset.analyticsSection || "",
      article_slug: target.dataset.analyticsSlug || "",
      article_category: target.dataset.analyticsArticleCategory || "",
      article_topic: target.dataset.analyticsArticleTopic || "",
    });
  });

  const articleView = document.querySelector("[data-analytics-view='article']");
  if (articleView) {
    trackEvent("view_noticia", {
      event_category: "content",
      event_label: articleView.dataset.analyticsSlug || "",
      article_slug: articleView.dataset.analyticsSlug || "",
      article_category: articleView.dataset.analyticsArticleCategory || "",
      article_topic: articleView.dataset.analyticsArticleTopic || "",
    });
  }

  const buttons = document.querySelectorAll("[data-load-more-button]");

  buttons.forEach((button) => {
    const targetId = button.getAttribute("data-load-more-target");
    const target = targetId ? document.getElementById(targetId) : null;
    if (!target) {
      button.remove();
      return;
    }

    const batchSize = Number.parseInt(button.getAttribute("data-batch-size") || "6", 10);
    const defaultLabel = button.getAttribute("data-label-default") || button.textContent.trim();

    const updateState = () => {
      const hiddenItems = target.querySelectorAll("[data-load-more-item].is-hidden");
      if (!hiddenItems.length) {
        const wrapper = button.closest(".portal-category-loadmore");
        if (wrapper) {
          wrapper.remove();
        } else {
          button.remove();
        }
        return;
      }

      button.textContent = `${defaultLabel} (${hiddenItems.length})`;
    };

    button.addEventListener("click", () => {
      const hiddenItems = Array.from(target.querySelectorAll("[data-load-more-item].is-hidden"));
      hiddenItems.slice(0, batchSize).forEach((item) => item.classList.remove("is-hidden"));
      trackEvent(button.dataset.analyticsEvent || "click_carregar_mais_noticias", {
        event_category: button.dataset.analyticsCategory || "engagement",
        event_label: button.dataset.analyticsLabel || defaultLabel,
        revealed_items: Math.min(hiddenItems.length, batchSize),
        hidden_items_remaining: Math.max(hiddenItems.length - batchSize, 0),
      });
      updateState();
    });

    updateState();
  });

  const getAlertsPerView = () => {
    if (window.innerWidth <= 760) {
      return 1;
    }
    if (window.innerWidth <= 1080) {
      return 2;
    }
    return 3;
  };

  document.querySelectorAll("[data-alerts-carousel]").forEach((carousel) => {
    const viewport = carousel.querySelector("[data-alerts-viewport]");
    const track = carousel.querySelector("[data-alerts-track]");
    const prevButton = carousel.querySelector("[data-alerts-prev]");
    const nextButton = carousel.querySelector("[data-alerts-next]");
    const dotsHost = carousel.querySelector("[data-alerts-dots]");
    const slides = Array.from(carousel.querySelectorAll("[data-alerts-slide]"));

    if (!viewport || !track || !prevButton || !nextButton || !dotsHost || !slides.length) {
      return;
    }

    let currentPage = 0;
    let pageCount = 1;

    const buildDots = () => {
      dotsHost.innerHTML = "";
      for (let index = 0; index < pageCount; index += 1) {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.className = "news-alerts-carousel__dot";
        dot.setAttribute("aria-label", `Ir para grupo ${index + 1} de alertas`);
        dot.addEventListener("click", () => {
          currentPage = index;
          updateCarousel();
        });
        dotsHost.appendChild(dot);
      }
    };

    const updateCarousel = () => {
      const gap = Number.parseFloat(window.getComputedStyle(track).columnGap || window.getComputedStyle(track).gap || "0");
      const offset = currentPage * (viewport.clientWidth + gap);
      track.style.transform = `translateX(-${offset}px)`;

      const dots = Array.from(dotsHost.children);
      dots.forEach((dot, index) => {
        dot.classList.toggle("is-active", index === currentPage);
      });

      prevButton.disabled = currentPage <= 0;
      nextButton.disabled = currentPage >= pageCount - 1;
    };

    const recalcCarousel = () => {
      const perView = getAlertsPerView();
      pageCount = Math.max(1, Math.ceil(slides.length / perView));
      currentPage = Math.min(currentPage, pageCount - 1);
      buildDots();
      updateCarousel();
    };

    prevButton.addEventListener("click", () => {
      currentPage = Math.max(0, currentPage - 1);
      updateCarousel();
    });

    nextButton.addEventListener("click", () => {
      currentPage = Math.min(pageCount - 1, currentPage + 1);
      updateCarousel();
    });

    // Prevent click-through after mouse drag on carousel links
    let dragStartX = 0;
    let dragStartY = 0;
    let isDragging = false;
    carousel.addEventListener("pointerdown", (e) => {
      dragStartX = e.clientX;
      dragStartY = e.clientY;
      isDragging = false;
    }, { passive: true });
    carousel.addEventListener("pointermove", (e) => {
      if (Math.abs(e.clientX - dragStartX) > 5 || Math.abs(e.clientY - dragStartY) > 5) {
        isDragging = true;
      }
    }, { passive: true });
    carousel.addEventListener("click", (e) => {
      if (isDragging) {
        e.preventDefault();
        e.stopPropagation();
        isDragging = false;
      }
    }, true);

    // Touch swipe on mobile
    let touchStartX = 0;
    viewport.addEventListener("touchstart", (e) => {
      touchStartX = e.touches[0].clientX;
    }, { passive: true });
    viewport.addEventListener("touchend", (e) => {
      const diff = touchStartX - e.changedTouches[0].clientX;
      if (Math.abs(diff) > 40) {
        if (diff > 0) {
          currentPage = Math.min(pageCount - 1, currentPage + 1);
        } else {
          currentPage = Math.max(0, currentPage - 1);
        }
        updateCarousel();
      }
    }, { passive: true });

    window.addEventListener("resize", recalcCarousel, { passive: true });
    recalcCarousel();
  });
});
