/* Creator OS Scheduling Dashboard — vanilla JS, no dependencies */

const App = (function () {
  "use strict";

  const PLATFORMS = ["instagram", "tiktok", "pinterest", "youtube"];
  const CAPTION_LIMITS = {
    instagram: 2200,
    tiktok: 4000,
    pinterest: 500,
    youtube: 5000,
  };

  let state = {
    view: "queue",
    queue: [],
    publishingPlan: {},
    credentials: {},
    calendarMonth: new Date().getMonth(),
    calendarYear: new Date().getFullYear(),
    editingItemId: null,
    editingPlatform: null,
  };

  // ── API helpers ────────────────────────────────────────────────

  async function api(method, path, body) {
    const opts = { method, headers: { "Content-Type": "application/json" } };
    if (body) opts.body = JSON.stringify(body);
    try {
      const res = await fetch(path, opts);
      let data = null;
      try {
        data = await res.json();
      } catch (e) {
        data = null;
      }
      if (!res.ok) {
        return { ok: false, error: (data && data.error) || "HTTP " + res.status };
      }
      return data == null ? { ok: true } : data;
    } catch (e) {
      return { ok: false, error: "network error: " + (e && e.message ? e.message : e) };
    }
  }

  async function loadQueue() {
    const data = await api("GET", "/api/queue");
    state.queue = data.queue || [];
  }

  async function loadPublishingPlan() {
    state.publishingPlan = await api("GET", "/api/publishing-plan");
  }

  async function loadCredentials() {
    state.credentials = await api("GET", "/api/credentials-status");
  }

  // ── Toast notifications ────────────────────────────────────────

  function toast(message, type) {
    type = type || "success";
    var container = document.getElementById("toasts");
    var el = document.createElement("div");
    el.className = "toast " + type;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(function () {
      el.remove();
    }, 3000);
  }

  // ── Navigation ─────────────────────────────────────────────────

  function switchView(view) {
    state.view = view;
    document.querySelectorAll("#nav button").forEach(function (btn) {
      btn.classList.toggle("active", btn.dataset.view === view);
    });
    render();
  }

  // ── Render dispatcher ──────────────────────────────────────────

  function render() {
    var main = document.getElementById("main-content");
    switch (state.view) {
      case "queue":
        renderQueue(main);
        break;
      case "calendar":
        renderCalendar(main);
        break;
      case "status":
        renderStatus(main);
        break;
      case "ar":
        renderAr(main);
        break;
      case "credentials":
        renderCredentials(main);
        break;
    }
  }

  // ── Queue view ─────────────────────────────────────────────────

  function renderQueue(container) {
    var items = state.queue;
    var html = '<div class="queue-header">';
    html += "<h2>Content Queue</h2>";
    html += "</div>";

    if (items.length === 0) {
      html += '<div class="queue-empty">';
      html +=
        '<svg><use href="/static/icons.svg#icon-list"/></svg>';
      html += "<p>No content in the queue yet.</p>";
      html +=
        "<p>Use the content-distributor skill to add posts, or schedule content via the MCP tools.</p>";
      html += "</div>";
      container.innerHTML = html;
      return;
    }

    items.forEach(function (item) {
      html += '<div class="card">';
      html += '<div class="card-header">';
      html += "<div>";
      html +=
        '<div class="card-title">' + escapeHtml(item.title) + "</div>";
      html +=
        '<div class="card-meta">Source: ' +
        escapeHtml(item.source || "manual") +
        " &middot; " +
        formatDate(item.created_at) +
        "</div>";
      html += "</div>";
      html += '<div class="card-actions">';
      html +=
        '<button class="btn btn-danger btn-sm" data-action="delete" data-item-id="' +
        escapeHtml(item.id) +
        '"><svg><use href="/static/icons.svg#icon-trash"/></svg></button>';
      html += "</div></div>";

      html += '<div class="platforms-grid">';
      PLATFORMS.forEach(function (plat) {
        var pd = (item.platforms || {})[plat] || {};
        var enabled = !!pd.enabled;
        var status = pd.status || "draft";

        html +=
          '<div class="platform-row' + (enabled ? " enabled" : "") + '">';
        html +=
          '<svg class="platform-icon ' +
          plat +
          '"><use href="/static/icons.svg#icon-' +
          plat +
          '"/></svg>';
        html += '<div class="platform-info">';
        html += '<div class="platform-name">' + capitalize(plat) + "</div>";
        html += '<div class="platform-status">';
        html += '<span class="status-dot ' + status + '"></span> ';
        html += statusLabel(status);
        if (pd.scheduled_datetime) {
          html += " &middot; " + formatDateTime(pd.scheduled_datetime);
        }
        html += "</div></div>";

        html += '<label class="toggle">';
        html +=
          '<input type="checkbox"' +
          (enabled ? " checked" : "") +
          ' data-action="toggle" data-item-id="' +
          escapeHtml(item.id) +
          '" data-platform="' +
          plat +
          '">';
        html += '<span class="toggle-track"></span>';
        html += "</label>";

        if (enabled) {
          html +=
            '<button class="platform-edit-btn" data-action="edit" data-item-id="' +
            escapeHtml(item.id) +
            '" data-platform="' +
            plat +
            '" title="Edit">';
          html +=
            '<svg><use href="/static/icons.svg#icon-edit"/></svg>';
          html += "</button>";
        }

        html += "</div>";
      });
      html += "</div>";

      var anyEnabled = PLATFORMS.some(function (p) {
        return (item.platforms || {})[p] && (item.platforms || {})[p].enabled;
      });
      if (anyEnabled) {
        html +=
          '<div style="margin-top:14px;text-align:right">';
        html +=
          '<button class="btn btn-primary" data-action="schedule-all" data-item-id="' +
          escapeHtml(item.id) +
          '">Confirm &amp; Schedule</button>';
        html += "</div>";
      }

      html += "</div>";
    });

    container.innerHTML = html;
  }

  // ── Calendar view ──────────────────────────────────────────────

  function renderCalendar(container) {
    var month = state.calendarMonth;
    var year = state.calendarYear;
    var monthNames = [
      "January", "February", "March", "April", "May", "June",
      "July", "August", "September", "October", "November", "December",
    ];
    var dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

    var html = '<div class="calendar-header">';
    html += "<h2>Content Calendar</h2>";
    html += '<div class="calendar-nav">';
    html +=
      '<button onclick="App.calendarPrev()"><svg><use href="/static/icons.svg#icon-chevron-left"/></svg></button>';
    html +=
      "<span>" + monthNames[month] + " " + year + "</span>";
    html +=
      '<button onclick="App.calendarNext()"><svg><use href="/static/icons.svg#icon-chevron-right"/></svg></button>';
    html += "</div></div>";

    html += '<div class="calendar-grid">';
    dayNames.forEach(function (d) {
      html += '<div class="calendar-day-header">' + d + "</div>";
    });

    var firstDay = new Date(year, month, 1).getDay();
    var daysInMonth = new Date(year, month + 1, 0).getDate();
    var prevDays = new Date(year, month, 0).getDate();
    var today = new Date();
    var todayStr =
      today.getFullYear() +
      "-" +
      pad(today.getMonth() + 1) +
      "-" +
      pad(today.getDate());

    var events = buildCalendarEvents();

    for (var i = 0; i < firstDay; i++) {
      var pDay = prevDays - firstDay + i + 1;
      html += '<div class="calendar-day other-month">';
      html += '<div class="calendar-date">' + pDay + "</div>";
      html += "</div>";
    }

    for (var d = 1; d <= daysInMonth; d++) {
      var dateStr = year + "-" + pad(month + 1) + "-" + pad(d);
      var isToday = dateStr === todayStr;
      html +=
        '<div class="calendar-day' +
        (isToday ? " today" : "") +
        '">';
      html += '<div class="calendar-date">' + d + "</div>";
      (events[dateStr] || []).forEach(function (ev) {
        html +=
          '<div class="calendar-event ' +
          ev.platform +
          '" title="' +
          escapeHtml(ev.title) +
          " (" +
          capitalize(ev.platform) +
          ')">';
        html += escapeHtml(ev.title);
        html += "</div>";
      });
      html += "</div>";
    }

    var totalCells = firstDay + daysInMonth;
    var remaining = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    for (var r = 1; r <= remaining; r++) {
      html += '<div class="calendar-day other-month">';
      html += '<div class="calendar-date">' + r + "</div>";
      html += "</div>";
    }

    html += "</div>";
    container.innerHTML = html;
  }

  function buildCalendarEvents() {
    var events = {};
    state.queue.forEach(function (item) {
      PLATFORMS.forEach(function (plat) {
        var pd = (item.platforms || {})[plat] || {};
        if (pd.enabled && pd.scheduled_datetime) {
          var dateKey = pd.scheduled_datetime.substring(0, 10);
          if (!events[dateKey]) events[dateKey] = [];
          events[dateKey].push({
            title: item.title,
            platform: plat,
            itemId: item.id,
          });
        }
      });
    });
    return events;
  }

  // ── Status view ────────────────────────────────────────────────

  function renderStatus(container) {
    var html = '<div class="status-header">';
    html += "<h2>Post Status</h2>";
    html +=
      '<button class="btn" onclick="App.refresh()"><svg><use href="/static/icons.svg#icon-refresh"/></svg> Refresh</button>';
    html += "</div>";

    var rows = [];
    state.queue.forEach(function (item) {
      PLATFORMS.forEach(function (plat) {
        var pd = (item.platforms || {})[plat] || {};
        if (pd.enabled) {
          rows.push({
            title: item.title,
            platform: plat,
            status: pd.status || "draft",
            scheduled: pd.scheduled_datetime,
            permalink: pd.permalink,
            postId: pd.post_id,
            error: pd.error,
          });
        }
      });
    });

    if (rows.length === 0) {
      html += '<div class="queue-empty">';
      html += "<p>No enabled posts to show.</p>";
      html += "</div>";
      container.innerHTML = html;
      return;
    }

    html += '<div class="status-table-wrap">';
    html += '<table class="status-table">';
    html += "<thead><tr>";
    html += "<th>Title</th><th>Platform</th><th>Status</th>";
    html += "<th>Scheduled</th><th>Permalink</th><th>Error</th>";
    html += "</tr></thead><tbody>";

    rows.forEach(function (row) {
      html += "<tr>";
      html += "<td>" + escapeHtml(row.title) + "</td>";
      html +=
        '<td><svg class="platform-icon ' +
        row.platform +
        '" style="width:16px;height:16px;vertical-align:middle"><use href="/static/icons.svg#icon-' +
        row.platform +
        '"/></svg> ' +
        capitalize(row.platform) +
        "</td>";
      html +=
        '<td><span class="status-badge ' +
        row.status +
        '">' +
        statusLabel(row.status) +
        "</span></td>";
      html +=
        "<td>" +
        (row.scheduled ? formatDateTime(row.scheduled) : "-") +
        "</td>";
      html += "<td>";
      if (row.permalink) {
        html +=
          '<a class="permalink-link" href="' +
          escapeHtml(row.permalink) +
          '" target="_blank" rel="noopener">';
        html +=
          '<svg><use href="/static/icons.svg#icon-link"/></svg> View';
        html += "</a>";
      } else {
        html += "-";
      }
      html += "</td>";
      html +=
        "<td>" +
        (row.error
          ? '<span style="color:var(--error)">' +
            escapeHtml(row.error) +
            "</span>"
          : "-") +
        "</td>";
      html += "</tr>";
    });

    html += "</tbody></table></div>";
    container.innerHTML = html;
  }

  // ── Credentials view ──────────────────────────────────────────

  function loadAr() {
    return api("GET", "/api/ar").then(function (data) {
      state.ar = data;
    });
  }

  function renderAr(container) {
    var ar = state.ar;
    var html = '<div class="card"><h2>Accounts receivable</h2>';
    html += '<p class="muted">Real money data from your local records. Localhost only; ' +
            'nothing here is sent anywhere. Use the redacted CLI view for screenshots.</p>';
    if (!ar || ar.error) {
      html += '<p class="queue-empty">' + escapeHtml((ar && ar.error) || "Could not load the AR view.") + "</p></div>";
      container.innerHTML = html;
      return;
    }
    html += "<p>As of " + escapeHtml(ar.as_of) + " &middot; total outstanding: <strong>" +
            escapeHtml(ar.total_outstanding) + "</strong></p>";
    var bucketLabels = {
      current: "Current",
      "1_to_30": "1 to 30 days",
      "31_to_60": "31 to 60 days",
      "61_to_90": "61 to 90 days",
      over_90: "Over 90 days"
    };
    html += '<div class="status-table-wrap"><table class="status-table">';
    html += "<thead><tr><th>Bucket</th><th>Invoices</th><th>Total</th></tr></thead><tbody>";
    Object.keys(bucketLabels).forEach(function (key) {
      var rows = (ar.buckets && ar.buckets[key]) || [];
      html += "<tr><td>" + bucketLabels[key] + "</td><td>" + rows.length + "</td><td>" +
              escapeHtml((ar.bucket_totals && ar.bucket_totals[key]) || "0.00") + "</td></tr>";
    });
    html += "</tbody></table></div>";

    var queue = ar.action_queue || [];
    html += "<h3>Chase queue</h3>";
    if (!queue.length) {
      html += '<p class="queue-empty">Nothing overdue. Nice.</p>';
    } else {
      html += '<div class="status-table-wrap"><table class="status-table">';
      html += "<thead><tr><th>Invoice</th><th>Brand</th><th>Amount</th>" +
              "<th>Days past due</th><th>Penalty accrued</th><th>Chase by</th></tr></thead><tbody>";
      queue.forEach(function (row) {
        html += "<tr>";
        html += "<td>" + escapeHtml(row.invoice_id || "") + "</td>";
        html += "<td>" + escapeHtml(row.brand_name || "") + "</td>";
        html += "<td>" + escapeHtml(row.amount || "") + "</td>";
        html += "<td>" + escapeHtml(String(row.days_past_due)) + "</td>";
        html += "<td>" + escapeHtml(row.accrued_penalty || "0.00") + "</td>";
        html += "<td>" + escapeHtml(row.chase_send_by || "") + "</td>";
        html += "</tr>";
      });
      html += "</tbody></table></div>";
    }
    var disputed = ar.disputed || [];
    if (disputed.length) {
      html += "<h3>Disputed (excluded from totals)</h3><ul>";
      disputed.forEach(function (row) {
        html += "<li>" + escapeHtml(row.invoice_id || "") + " &middot; " +
                escapeHtml(row.brand_name || "") + " &middot; " + escapeHtml(row.amount || "") + "</li>";
      });
      html += "</ul>";
    }
    html += "</div>";
    container.innerHTML = html;
  }

  function renderCredentials(container) {
    var html = "<h2>Platform Credentials</h2>";
    html +=
      '<p style="color:var(--text-muted);margin:8px 0 0">API credential status for direct publishing. Run <code>python3 tools/wizard.py</code> to configure.</p>';

    html += '<div class="creds-grid">';
    PLATFORMS.forEach(function (plat) {
      var hasCreds = state.credentials[plat] || false;
      var plan = state.publishingPlan[plat] || {};
      var tier = plan.tier || "manual";

      html += '<div class="cred-card">';
      html += '<div class="cred-card-header">';
      html +=
        '<svg class="platform-icon ' +
        plat +
        '"><use href="/static/icons.svg#icon-' +
        plat +
        '"/></svg>';
      html += "<h3>" + capitalize(plat) + "</h3>";
      html += "</div>";

      html +=
        '<div class="cred-status ' +
        (hasCreds ? "connected" : "not-connected") +
        '">';
      if (hasCreds) {
        html +=
          '<svg><use href="/static/icons.svg#icon-check"/></svg> Credentials configured';
      } else {
        html +=
          '<svg><use href="/static/icons.svg#icon-alert"/></svg> Not configured';
      }
      html += "</div>";

      html += '<div class="cred-tier">';
      html +=
        "Publishing tier: <strong>" +
        (tier === "direct_api" ? "Direct API" : "Manual") +
        "</strong>";
      html += "</div>";

      if (!hasCreds) {
        html += '<div class="cred-action">';
        html += '<button class="btn btn-sm" onclick="App.openSetupInfo(\'' + plat + '\')">';
        html += "Setup Guide</button>";
        html += "</div>";
      }

      html += "</div>";
    });
    html += "</div>";

    html +=
      '<div style="margin-top:24px;padding:16px;background:var(--bg);border-radius:var(--radius);border:1px solid var(--border)">';
    html +=
      '<p style="font-size:13px;color:var(--text-muted)"><strong>Note:</strong> Confirming a post runs the FTC and AIGC compliance checks and schedules it. Direct API publishing is not enabled yet, so when a scheduled time passes the post is marked <strong>Ready to post</strong> for you to publish manually. Keep the dashboard running so scheduled items advance to Ready to post on time; if it is not running, they advance the next time you start it.</p>';
    html += "</div>";

    container.innerHTML = html;
  }

  // ── Modal (edit platform post) ─────────────────────────────────

  function openEdit(itemId, platform) {
    state.editingItemId = itemId;
    state.editingPlatform = platform;

    var item = state.queue.find(function (q) {
      return q.id === itemId;
    });
    if (!item) return;

    var pd = (item.platforms || {})[platform] || {};

    document.getElementById("modal-title").textContent =
      "Edit " + capitalize(platform) + " Post";

    document.getElementById("edit-caption").value = pd.caption || "";
    document.getElementById("edit-hashtags").value = (pd.hashtags || []).join(
      ", "
    );
    document.getElementById("edit-content-type").value =
      pd.content_type || "";
    document.getElementById("edit-media-url").value = pd.media_url || "";
    document.getElementById("edit-ftc").value = pd.ftc_disclosure || "";
    document.getElementById("edit-aigc").checked = !!pd.is_aigc;

    var aigcGroup = document.getElementById("aigc-group");
    aigcGroup.style.display = platform === "tiktok" ? "block" : "none";

    if (pd.scheduled_datetime) {
      var dt = pd.scheduled_datetime.substring(0, 16);
      document.getElementById("edit-schedule").value = dt;
    } else {
      document.getElementById("edit-schedule").value = "";
    }

    updateCharCount();
    document.getElementById("edit-modal").classList.add("open");
  }

  function closeModal() {
    document.getElementById("edit-modal").classList.remove("open");
    state.editingItemId = null;
    state.editingPlatform = null;
  }

  function updateCharCount() {
    var caption = document.getElementById("edit-caption").value;
    var plat = state.editingPlatform || "instagram";
    var limit = CAPTION_LIMITS[plat] || 2200;
    var el = document.getElementById("caption-count");
    el.textContent = caption.length + " / " + limit;
    el.className = "char-count" + (caption.length > limit ? " over" : "");
  }

  async function saveEdit() {
    var itemId = state.editingItemId;
    var platform = state.editingPlatform;
    if (!itemId || !platform) return;

    var caption = document.getElementById("edit-caption").value;

    var limit = CAPTION_LIMITS[platform] || 2200;
    if (caption.length > limit) {
      toast(
        capitalize(platform) +
          " caption is " +
          caption.length +
          " / " +
          limit +
          " characters. Trim it before saving.",
        "error"
      );
      return;
    }

    var hashtagsRaw = document.getElementById("edit-hashtags").value;
    var hashtags = hashtagsRaw
      ? hashtagsRaw.split(",").map(function (h) {
          return h.trim();
        }).filter(Boolean)
      : [];
    var contentType =
      document.getElementById("edit-content-type").value || null;
    var mediaUrl =
      document.getElementById("edit-media-url").value || null;
    var ftc = document.getElementById("edit-ftc").value || null;
    var aigc = document.getElementById("edit-aigc").checked;
    var scheduleVal = document.getElementById("edit-schedule").value;

    await api("POST", "/api/update-caption", {
      item_id: itemId,
      platform: platform,
      caption: caption,
      hashtags: hashtags,
      content_type: contentType,
      media_url: mediaUrl,
      ftc_disclosure: ftc,
      is_aigc: aigc,
    });

    if (scheduleVal) {
      await api("POST", "/api/update-schedule", {
        item_id: itemId,
        platform: platform,
        scheduled_datetime: scheduleVal + ":00",
      });
    }

    closeModal();
    await loadQueue();
    render();
    toast("Saved " + capitalize(platform) + " post details");
  }

  // ── Actions ────────────────────────────────────────────────────

  async function togglePlatform(itemId, platform, enabled) {
    await api("POST", "/api/toggle-platform", {
      item_id: itemId,
      platform: platform,
      enabled: enabled,
    });
    await loadQueue();
    render();
  }

  async function scheduleAll(itemId) {
    var item = state.queue.find(function (q) {
      return q.id === itemId;
    });
    if (!item) return;

    var scheduled = 0;
    var errors = [];

    for (var i = 0; i < PLATFORMS.length; i++) {
      var plat = PLATFORMS[i];
      var pd = (item.platforms || {})[plat] || {};
      if (!pd.enabled) continue;

      var res = await api("POST", "/api/schedule", {
        item_id: itemId,
        platform: plat,
      });

      if (res.ok) {
        scheduled++;
      } else {
        errors.push(capitalize(plat) + ": " + (res.error || "unknown error"));
      }
    }

    await loadQueue();
    render();

    if (scheduled > 0) {
      toast(
        "Scheduled " +
          scheduled +
          " platform" +
          (scheduled > 1 ? "s" : "") +
          " (human review confirmed)"
      );
    }
    if (errors.length > 0) {
      toast(errors.join("; "), "error");
    }
  }

  async function deleteItem(itemId) {
    if (!confirm("Delete this content from the queue?")) return;
    await api("POST", "/api/delete-item", { item_id: itemId });
    await loadQueue();
    render();
    toast("Item removed from queue");
  }

  async function refresh() {
    await loadQueue();
    await loadPublishingPlan();
    await loadCredentials();
    render();
    toast("Refreshed");
  }

  // ── Calendar navigation ────────────────────────────────────────

  function calendarPrev() {
    state.calendarMonth--;
    if (state.calendarMonth < 0) {
      state.calendarMonth = 11;
      state.calendarYear--;
    }
    render();
  }

  function calendarNext() {
    state.calendarMonth++;
    if (state.calendarMonth > 11) {
      state.calendarMonth = 0;
      state.calendarYear++;
    }
    render();
  }

  // ── Setup info ─────────────────────────────────────────────────

  function openSetupInfo(platform) {
    window.open(
      "http://localhost:8765/publishing-setup/" + platform,
      "_blank"
    );
  }

  // ── Utility ────────────────────────────────────────────────────

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  var STATUS_LABELS = {
    draft: "Draft",
    scheduled: "Scheduled",
    ready_to_post: "Ready to post",
    published: "Published",
    failed: "Failed",
    awaiting_human_confirmation: "Awaiting confirmation",
  };

  function statusLabel(s) {
    return STATUS_LABELS[s] || capitalize(s);
  }

  function capitalize(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
  }

  function pad(n) {
    return n < 10 ? "0" + n : "" + n;
  }

  function formatDate(iso) {
    if (!iso) return "";
    try {
      var d = new Date(iso);
      return d.toLocaleDateString();
    } catch (e) {
      return iso;
    }
  }

  function formatDateTime(iso) {
    if (!iso) return "";
    try {
      var d = new Date(iso);
      return (
        d.toLocaleDateString() +
        " " +
        d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      );
    } catch (e) {
      return iso;
    }
  }

  // ── Init ───────────────────────────────────────────────────────

  async function init() {
    document.querySelectorAll("#nav button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        switchView(btn.dataset.view);
      });
    });

    // Delegated handlers for queue-view actions. Data flows via data-* attributes
    // (not HTML-parsed) instead of inline onclick string concatenation, so a queue
    // item id can never break out of an attribute and inject script.
    var main = document.getElementById("main-content");
    main.addEventListener("click", function (e) {
      var el = e.target.closest("[data-action]");
      if (!el) return;
      var action = el.dataset.action;
      var id = el.dataset.itemId;
      var plat = el.dataset.platform;
      if (action === "delete") deleteItem(id);
      else if (action === "edit") openEdit(id, plat);
      else if (action === "schedule-all") scheduleAll(id);
    });
    main.addEventListener("change", function (e) {
      var el = e.target.closest('[data-action="toggle"]');
      if (!el) return;
      togglePlatform(el.dataset.itemId, el.dataset.platform, el.checked);
    });

    document
      .getElementById("edit-caption")
      .addEventListener("input", updateCharCount);

    document
      .getElementById("edit-modal")
      .addEventListener("click", function (e) {
        if (e.target === this) closeModal();
      });

    await Promise.all([loadQueue(), loadPublishingPlan(), loadCredentials(), loadAr()]);
    render();
  }

  document.addEventListener("DOMContentLoaded", init);

  return {
    switchView: switchView,
    openEdit: openEdit,
    closeModal: closeModal,
    saveEdit: saveEdit,
    togglePlatform: togglePlatform,
    scheduleAll: scheduleAll,
    deleteItem: deleteItem,
    refresh: refresh,
    calendarPrev: calendarPrev,
    calendarNext: calendarNext,
    openSetupInfo: openSetupInfo,
  };
})();
