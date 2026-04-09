document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  const analyticsMeasurementId = body.dataset.analyticsMeasurementId || "";
  const cookieName = body.dataset.cookieConsentName || "ncfly_cookie_preferences";
  const cookieVersion = body.dataset.cookieConsentVersion || "2026-04";
  const cookieMaxAgeDays = Number.parseInt(body.dataset.cookieConsentMaxAge || "180", 10);
  const metricsEndpoint = body.dataset.publicMetricsEndpoint || "";

  const banner = document.querySelector("[data-cookie-banner]");
  const modal = document.querySelector("[data-cookie-modal]");
  let analyticsAvailable =
    typeof window !== "undefined" &&
    typeof window.gtag === "function" &&
    Boolean(window.NCFlyAnalytics?.measurementId);
  const desktopAds = Array.from(document.querySelectorAll(".adsbygoogle[data-ad-client]"));
  const desktopAdsMediaQuery = window.matchMedia
    ? window.matchMedia("(min-width: 1440px)")
    : null;
  const scheduleNonCritical = (callback, timeout = 1200) => {
    if ("requestIdleCallback" in window) {
      window.requestIdleCallback(() => callback(), { timeout });
      return;
    }
    window.setTimeout(callback, 1);
  };

  const loadDesktopAds = () => {
    if (!desktopAds.length) {
      return;
    }

    const isDesktopViewport = desktopAdsMediaQuery
      ? desktopAdsMediaQuery.matches
      : window.innerWidth >= 1440;
    const reducedDataMode = Boolean(navigator.connection?.saveData);
    const adClient = desktopAds[0].dataset.adClient || "";

    if (!isDesktopViewport || reducedDataMode || !adClient) {
      return;
    }

    const initializeSlots = () => {
      desktopAds.forEach((slot) => {
        if (slot.dataset.adInitialized === "1") {
          return;
        }
        try {
          (window.adsbygoogle = window.adsbygoogle || []).push({});
          slot.dataset.adInitialized = "1";
        } catch {}
      });
    };

    if (document.querySelector("script[data-portal-ads-script='1']")) {
      initializeSlots();
      return;
    }

    const adScript = document.createElement("script");
    adScript.async = true;
    adScript.crossOrigin = "anonymous";
    adScript.dataset.portalAdsScript = "1";
    adScript.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(adClient)}`;
    adScript.addEventListener("load", initializeSlots, { once: true });

    const injectScript = () => {
      document.head.appendChild(adScript);
    };

    if ("requestIdleCallback" in window) {
      window.requestIdleCallback(injectScript, { timeout: 2000 });
      return;
    }

    window.setTimeout(injectScript, 1200);
  };

  const scheduleDesktopAdsLoad = () => {
    scheduleNonCritical(loadDesktopAds, 2200);
  };

  if (document.readyState === "complete") {
    scheduleDesktopAdsLoad();
  } else {
    window.addEventListener("load", scheduleDesktopAdsLoad, { once: true });
  }
  if (desktopAdsMediaQuery?.addEventListener) {
    desktopAdsMediaQuery.addEventListener("change", (event) => {
      if (event.matches) {
        scheduleDesktopAdsLoad();
      }
    });
  }

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

  const enableAnalytics = () => {
    if (!analyticsMeasurementId) {
      return;
    }

    const bootAnalytics = () => {
      window.dataLayer = window.dataLayer || [];
      window.gtag = window.gtag || function gtag(){ window.dataLayer.push(arguments); };
      window.gtag("js", new Date());
      window.gtag("config", analyticsMeasurementId);
      window.gtag("consent", "update", { analytics_storage: "granted" });
      window.NCFlyAnalytics = { measurementId: analyticsMeasurementId };
      analyticsAvailable = true;
    };

    if (analyticsAvailable) {
      try {
        window.gtag("consent", "update", { analytics_storage: "granted" });
      } catch {}
      return;
    }

    if (typeof window.gtag === "function") {
      bootAnalytics();
      return;
    }

    const existingScript = document.querySelector("script[data-portal-analytics-script='1']");
    if (existingScript) {
      return;
    }

    const analyticsScript = document.createElement("script");
    analyticsScript.async = true;
    analyticsScript.dataset.portalAnalyticsScript = "1";
    analyticsScript.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(analyticsMeasurementId)}`;
    analyticsScript.addEventListener("load", bootAnalytics, { once: true });
    document.head.appendChild(analyticsScript);
  };

  const disableAnalytics = () => {
    analyticsAvailable = false;
    if (typeof window.gtag === "function") {
      try {
        window.gtag("consent", "update", { analytics_storage: "denied" });
      } catch {}
    }
  };

  const applyPreferences = (preferences) => {
    writePreferences(preferences);
    hideBanner();
    closeModal();
    syncCookieInputs();

    if (preferences.analytics) {
      enableAnalytics();
    } else {
      disableAnalytics();
    }
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
        applyPreferences({ essential: true, analytics: true });
        return;
      }

      if (action === "reject") {
        applyPreferences({ essential: true, analytics: false });
        return;
      }

      if (action === "save") {
        const analyticsInput = document.querySelector("[data-cookie-setting='analytics']");
        applyPreferences({
          essential: true,
          analytics: Boolean(analyticsInput?.checked),
        });
      }
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

  const normalizeWhatsappNumber = (value) => {
    const digits = String(value || "").replace(/\D/g, "");
    if (digits.length === 10 || digits.length === 11) {
      return `55${digits}`;
    }
    return digits;
  };

  document.querySelectorAll("[data-alert-whatsapp]").forEach((link) => {
    const whatsappNumber = normalizeWhatsappNumber(link.dataset.whatsappNumber);
    const whatsappMessage = link.dataset.whatsappMessage || "";
    const alertLink = link.dataset.alertLink || "";

    if (!whatsappNumber) {
      link.remove();
      return;
    }

    let finalMessage = whatsappMessage.trim();
    if (alertLink) {
      const absoluteAlertLink = new URL(alertLink, window.location.origin).toString();
      finalMessage = `${finalMessage}\n\nLink do alerta: ${absoluteAlertLink}`;
    }

    link.href = `https://wa.me/${whatsappNumber}?text=${encodeURIComponent(finalMessage)}`;
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

  scheduleNonCritical(() => {
    // Ler mais no artigo (mobile)
    document.querySelectorAll("[data-article-readmore]").forEach((btn) => {
      const section = btn.closest("[data-article-content]");
      if (!section) return;
      btn.addEventListener("click", () => {
        section.setAttribute("data-expanded", "");
      });
    });

    // Mobile: expande cards 4-6 da home antes de carregar mais do servidor
    const mobileExpandBtn = document.querySelector("[data-home-mobile-expand]");
    if (mobileExpandBtn) {
      const mobileWrap = document.getElementById("home-mobile-expand-wrap");
      const grid = document.getElementById("home-latest-grid");
      mobileExpandBtn.addEventListener("click", () => {
        if (grid) grid.setAttribute("data-mobile-expanded", "");
        if (mobileWrap) mobileWrap.remove();
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
  });

  const getAlertsPerView = (carousel) => {
    const mobilePerView = Number.parseInt(carousel?.dataset.alertsPerViewMobile || "1", 10);
    const tabletPerView = Number.parseInt(carousel?.dataset.alertsPerViewTablet || "2", 10);
    const desktopPerView = Number.parseInt(carousel?.dataset.alertsPerViewDesktop || "3", 10);

    if (window.innerWidth <= 760) {
      return Number.isFinite(mobilePerView) && mobilePerView > 0 ? mobilePerView : 1;
    }
    if (window.innerWidth <= 1080) {
      return Number.isFinite(tabletPerView) && tabletPerView > 0 ? tabletPerView : 2;
    }
    return Number.isFinite(desktopPerView) && desktopPerView > 0 ? desktopPerView : 3;
  };

  const initAlertsCarousel = (carousel) => {
    if (!carousel || carousel.dataset.carouselInitialized === "1") {
      return;
    }
    carousel.dataset.carouselInitialized = "1";

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
      const perView = getAlertsPerView(carousel);
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

    let resizeFrame = 0;
    window.addEventListener("resize", () => {
      if (resizeFrame) {
        window.cancelAnimationFrame(resizeFrame);
      }
      resizeFrame = window.requestAnimationFrame(recalcCarousel);
    }, { passive: true });
    recalcCarousel();
  };

  const alertCarousels = Array.from(document.querySelectorAll("[data-alerts-carousel]"));
  if ("IntersectionObserver" in window) {
    const carouselObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }
        initAlertsCarousel(entry.target);
        observer.unobserve(entry.target);
      });
    }, {
      rootMargin: "280px 0px",
    });

    alertCarousels.forEach((carousel) => {
      carouselObserver.observe(carousel);
    });
  } else {
    alertCarousels.forEach(initAlertsCarousel);
  }
});
