document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-acceptance-form]");
  if (!form) {
    return;
  }

  const fields = {};
  form.querySelectorAll("[data-acceptance-field]").forEach((input) => {
    fields[input.dataset.acceptanceField] = input;
  });

  const geolocationOptIn = form.querySelector("[data-acceptance-geolocation-optin]");
  const geolocationStatus = form.querySelector("[data-acceptance-geolocation-status]");
  let submitAfterGeolocation = false;

  const setField = (name, value) => {
    if (fields[name]) {
      fields[name].value = value ?? "";
    }
  };

  const setGeolocationStatus = (status, message) => {
    setField("geolocation_status", status);
    if (geolocationStatus) {
      geolocationStatus.textContent = message;
    }
  };

  const normalizeVersion = (match) => (match && match[1] ? match[1].replaceAll("_", ".") : "");

  const parseDeviceMetadata = () => {
    const userAgent = navigator.userAgent || "";
    const isTablet = /Tablet|iPad/i.test(userAgent) || (/Android/i.test(userAgent) && !/Mobile/i.test(userAgent));
    const isMobile = !isTablet && /Mobi|Android|iPhone|Windows Phone/i.test(userAgent);
    const deviceType = isTablet ? "tablet" : isMobile ? "mobile" : "desktop";

    let browserName = "Unknown";
    let browserVersion = "";
    const browserMatchers = [
      { name: "Edge", pattern: /Edg\/([\d.]+)/i },
      { name: "Opera", pattern: /OPR\/([\d.]+)/i },
      { name: "Chrome", pattern: /Chrome\/([\d.]+)/i },
      { name: "Firefox", pattern: /Firefox\/([\d.]+)/i },
      { name: "Safari", pattern: /Version\/([\d.]+).*Safari/i },
    ];
    for (const matcher of browserMatchers) {
      const match = userAgent.match(matcher.pattern);
      if (match) {
        browserName = matcher.name;
        browserVersion = normalizeVersion(match);
        break;
      }
    }

    let osName = "Unknown";
    let osVersion = "";
    const osMatchers = [
      { name: "Windows", pattern: /Windows NT ([\d.]+)/i },
      { name: "iOS", pattern: /iPhone OS ([\d_]+)/i },
      { name: "iPadOS", pattern: /CPU OS ([\d_]+)/i },
      { name: "Android", pattern: /Android ([\d.]+)/i },
      { name: "macOS", pattern: /Mac OS X ([\d_]+)/i },
      { name: "Linux", pattern: /Linux/i },
    ];
    for (const matcher of osMatchers) {
      const match = userAgent.match(matcher.pattern);
      if (match) {
        osName = matcher.name;
        osVersion = normalizeVersion(match);
        break;
      }
    }

    setField("device_type", deviceType);
    setField("browser_name", browserName);
    setField("browser_version", browserVersion);
    setField("os_name", osName);
    setField("os_version", osVersion);
    setField("device_language", navigator.language || "");
    setField("device_timezone", Intl.DateTimeFormat().resolvedOptions().timeZone || "");
    if (window.screen?.width && window.screen?.height) {
      setField("screen_resolution", `${window.screen.width}x${window.screen.height}`);
    }
  };

  const finalizeSubmitIfNeeded = () => {
    if (submitAfterGeolocation) {
      submitAfterGeolocation = false;
      form.requestSubmit();
    }
  };

  const requestGeolocation = () => {
    if (!geolocationOptIn?.checked) {
      setGeolocationStatus("not_requested", "Localizacao nao solicitada.");
      setField("latitude", "");
      setField("longitude", "");
      setField("geolocation_accuracy_meters", "");
      finalizeSubmitIfNeeded();
      return;
    }

    if (!navigator.geolocation) {
      setGeolocationStatus("unavailable", "Seu navegador nao oferece geolocalizacao.");
      finalizeSubmitIfNeeded();
      return;
    }

    setGeolocationStatus("pending", "Solicitando permissao de localizacao...");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setField("latitude", position.coords.latitude.toFixed(6));
        setField("longitude", position.coords.longitude.toFixed(6));
        setField("geolocation_accuracy_meters", position.coords.accuracy.toFixed(2));
        setGeolocationStatus("granted", "Localizacao autorizada e pronta para ser salva no aceite.");
        finalizeSubmitIfNeeded();
      },
      (error) => {
        const statusMap = {
          1: "denied",
          2: "unavailable",
          3: "timeout",
        };
        const messageMap = {
          1: "Permissao de localizacao negada. O aceite segue sem coordenadas.",
          2: "Nao foi possivel obter a localizacao neste dispositivo.",
          3: "A solicitacao de localizacao expirou. O aceite segue sem coordenadas.",
        };
        setField("latitude", "");
        setField("longitude", "");
        setField("geolocation_accuracy_meters", "");
        setGeolocationStatus(statusMap[error.code] || "error", messageMap[error.code] || "Nao foi possivel capturar a localizacao.");
        finalizeSubmitIfNeeded();
      },
      {
        enableHighAccuracy: false,
        timeout: 7000,
        maximumAge: 120000,
      }
    );
  };

  parseDeviceMetadata();

  if (geolocationOptIn) {
    geolocationOptIn.addEventListener("change", requestGeolocation);
  }

  form.addEventListener("submit", (event) => {
    if (!geolocationOptIn?.checked) {
      return;
    }
    const status = fields.geolocation_status?.value || "";
    if (status === "granted" || status === "denied" || status === "unavailable" || status === "timeout" || status === "error") {
      return;
    }
    event.preventDefault();
    submitAfterGeolocation = true;
    requestGeolocation();
  });
});
