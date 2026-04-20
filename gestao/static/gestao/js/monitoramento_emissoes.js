/* Monitoramento de passagens — UI:
 *  - Botao por linha: POST sync, atualiza badge inline.
 *  - Botao header: dispara em massa, polling do job no toast.
 *  - Carrega job em andamento ao abrir a pagina.
 *
 * Tudo idempotente / tolerante a HTML faltando (defesa contra mudanca de template).
 */
(function () {
  "use strict";

  var POLL_MS = 3500;
  var MAX_POLL_MINUTES = 30;

  function getCsrf() {
    return window.MONIT_CSRF_TOKEN || "";
  }

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function setBadge(cell, reservaText, vooText, quandoText, mudou) {
    if (!cell) return;
    var rsv = $("[data-monit-reserva]", cell);
    var voo = $("[data-monit-voo]", cell);
    var quando = $("[data-monit-quando]", cell);
    if (rsv && reservaText) rsv.textContent = reservaText;
    if (voo) voo.textContent = vooText || "";
    if (quando && quandoText) quando.textContent = quandoText;
    if (mudou) {
      cell.classList.add("is-changed");
      setTimeout(function () { cell.classList.remove("is-changed"); }, 12000);
    }
  }

  function formatarHora(iso) {
    if (!iso) return "Agora há pouco";
    try {
      var d = new Date(iso);
      var pad = function (n) { return String(n).padStart(2, "0"); };
      return pad(d.getDate()) + "/" + pad(d.getMonth() + 1) + "/" + d.getFullYear() + " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
    } catch (e) { return "Agora há pouco"; }
  }

  // -----------------------------------------------
  // CTA por linha
  // -----------------------------------------------
  function bindRowButtons() {
    $$("[data-atualizar-passagem]").forEach(function (btn) {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", function () {
        var url = btn.getAttribute("data-url");
        if (!url) return;
        var cell = btn.closest(".monit-cell");
        btn.disabled = true;
        btn.classList.add("is-loading");
        fetch(url, {
          method: "POST",
          headers: {
            "X-CSRFToken": getCsrf(),
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest"
          },
          credentials: "same-origin"
        })
          .then(function (r) { return r.json().catch(function () { return { sucesso: false, mensagem: "Resposta inválida (HTTP " + r.status + ")" }; }); })
          .then(function (data) {
            if (data && data.sucesso) {
              var depois = data.depois || {};
              setBadge(cell, depois.reserva, depois.voo, formatarHora(data.ultima_sincronizacao), data.teve_mudanca);
            } else {
              alert((data && data.mensagem) || "Falha ao atualizar status.");
            }
          })
          .catch(function (err) {
            alert("Erro de rede ao atualizar status.");
            console.error(err);
          })
          .finally(function () {
            btn.disabled = false;
            btn.classList.remove("is-loading");
          });
      });
    });
  }

  // -----------------------------------------------
  // CTA da empresa (massa) + toast + polling
  // -----------------------------------------------
  var pollingTimer = null;
  var pollingDeadline = 0;

  function showToast(state, msg, job) {
    var toast = $("#monit-toast");
    if (!toast) return;
    toast.hidden = false;
    toast.classList.remove("monit-toast--ok", "monit-toast--erro");
    if (state === "ok") toast.classList.add("monit-toast--ok");
    if (state === "erro") toast.classList.add("monit-toast--erro");
    var msgEl = $("[data-monit-msg]", toast);
    if (msgEl) msgEl.textContent = msg || "";
    if (job) updateToastJob(job);
  }

  function hideToast() {
    var toast = $("#monit-toast");
    if (toast) toast.hidden = true;
  }

  function updateToastJob(job) {
    var toast = $("#monit-toast");
    if (!toast) return;
    var bar = $("[data-monit-bar]", toast);
    var counts = $("[data-monit-counts]", toast);
    var msgEl = $("[data-monit-msg]", toast);
    if (bar) bar.style.width = (job.progresso_pct || 0) + "%";
    var processados = (job.ok || 0) + (job.erro || 0);
    if (counts) counts.textContent = processados + " de " + (job.total || 0) + " processados";
    if (msgEl) {
      if (job.status === "em_andamento") {
        msgEl.textContent = "Atualizando passagens em background. Pode continuar usando a tela.";
      } else if (job.status === "concluido") {
        var partes = [];
        if (job.com_mudanca) partes.push(job.com_mudanca + " com mudança");
        if (job.sem_mudanca) partes.push(job.sem_mudanca + " sem mudança");
        if (job.erro) partes.push(job.erro + " com erro");
        msgEl.textContent = "Concluído: " + (partes.length ? partes.join(", ") : "nada para atualizar") + ".";
      } else if (job.status === "interrompido") {
        msgEl.textContent = "Interrompido: " + (job.mensagem_erro || "tente novamente.");
      } else if (job.status === "erro") {
        msgEl.textContent = "Erro: " + (job.mensagem_erro || "consulte o log.");
      }
    }
  }

  function applyJobResultadoToRows(job) {
    if (!job || !Array.isArray(job.resultado)) return;
    job.resultado.forEach(function (item) {
      // Nao temos acomp_id nas linhas (so emissao_id). Quem aplica per-linha
      // sao os refreshes individuais; aqui so atualizamos o toast.
    });
  }

  function clearPolling() {
    if (pollingTimer) {
      clearTimeout(pollingTimer);
      pollingTimer = null;
    }
  }

  function pollJob(jobId, statusUrlTemplate) {
    var url = statusUrlTemplate.replace("/0/", "/" + jobId + "/");
    fetch(url, {
      method: "GET",
      headers: { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin"
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!data || !data.job) { hideToast(); return; }
        var job = data.job;
        updateToastJob(job);
        applyJobResultadoToRows(job);
        if (job.em_andamento) {
          if (Date.now() > pollingDeadline) {
            showToast("erro", "Polling excedeu " + MAX_POLL_MINUTES + " minutos. Verifique manualmente.", job);
            return;
          }
          pollingTimer = setTimeout(function () { pollJob(jobId, statusUrlTemplate); }, POLL_MS);
        } else {
          showToast(job.status === "concluido" ? "ok" : "erro", null, job);
        }
      })
      .catch(function (err) {
        console.error("Polling falhou:", err);
        // Re-tenta uma vez antes de desistir
        pollingTimer = setTimeout(function () { pollJob(jobId, statusUrlTemplate); }, POLL_MS * 2);
      });
  }

  function bindMassButton() {
    var btn = $("#btn-atualizar-todas-passagens");
    if (!btn) return;
    var dispatchUrl = btn.getAttribute("data-url");
    var statusUrlTemplate = btn.getAttribute("data-status-url-template");
    var jobAtualUrl = btn.getAttribute("data-job-atual-url");

    btn.addEventListener("click", function () {
      btn.disabled = true;
      btn.classList.add("is-loading");
      showToast("info", "Disparando atualização…");
      fetch(dispatchUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCsrf(),
          "Accept": "application/json",
          "X-Requested-With": "XMLHttpRequest"
        },
        credentials: "same-origin"
      })
        .then(function (r) { return r.json().catch(function () { return { sucesso: false, mensagem: "Resposta inválida (HTTP " + r.status + ")" }; }); })
        .then(function (data) {
          if (data && data.job) {
            updateToastJob(data.job);
            if (!data.sucesso) {
              showToast("info", data.mensagem || "Já existia atualização em andamento.", data.job);
            }
            clearPolling();
            pollingDeadline = Date.now() + MAX_POLL_MINUTES * 60 * 1000;
            if (data.job.em_andamento) {
              pollJob(data.job.id, statusUrlTemplate);
            }
          } else {
            showToast("erro", (data && data.mensagem) || "Falha ao disparar atualização.");
          }
        })
        .catch(function (err) {
          showToast("erro", "Erro de rede ao disparar atualização.");
          console.error(err);
        })
        .finally(function () {
          btn.disabled = false;
          btn.classList.remove("is-loading");
        });
    });

    var closeBtn = document.querySelector("[data-monit-toast-close]");
    if (closeBtn) closeBtn.addEventListener("click", function () { hideToast(); clearPolling(); });

    // Ao abrir a pagina, verifica se há job em andamento
    if (jobAtualUrl) {
      fetch(jobAtualUrl, { credentials: "same-origin", headers: { "Accept": "application/json" } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data && data.job && data.job.em_andamento) {
            pollingDeadline = Date.now() + MAX_POLL_MINUTES * 60 * 1000;
            showToast("info", "Há uma atualização em andamento.", data.job);
            pollJob(data.job.id, statusUrlTemplate);
          }
        })
        .catch(function () { /* silencioso */ });
    }
  }

  function init() {
    bindRowButtons();
    bindMassButton();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
