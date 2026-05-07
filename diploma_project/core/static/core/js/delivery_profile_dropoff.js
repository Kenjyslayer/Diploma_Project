/**
 * Preferred drop-off picker on registration (Nova Poshta / Ukrposhta).
 * Uses the same backend proxies as request/contribution.
 */
(function () {
  const root = document.getElementById("profile-dropoff-root");
  if (!root) return;

  const apiNovaCities = root.dataset.apiNovaCities;
  const apiNovaWh = root.dataset.apiNovaWarehouses;
  const apiUp = root.dataset.apiUp;
  const npConfigured = root.dataset.novaConfigured === "1";

  const elKind = document.getElementById("id_pref_delivery_kind");

  const elNpCityRef = document.getElementById("id_pref_np_city_ref");
  const elNpWhRef = document.getElementById("id_pref_np_warehouse_ref");
  const elNpLabel = document.getElementById("id_pref_np_label");

  const elUpPc = document.getElementById("id_pref_up_postcode");
  const elUpOfficeId = document.getElementById("id_pref_up_office_id");
  const elUpLabel = document.getElementById("id_pref_up_label");

  const panelNova = document.getElementById("pref-panel-nova");
  const panelUp = document.getElementById("pref-panel-ukrposhta");

  const npCitySearch = document.getElementById("pref-np-city-search");
  const npCityResults = document.getElementById("pref-np-city-results");
  const npWhPick = document.getElementById("pref-np-wh-pick");
  const npHint = document.getElementById("pref-np-api-hint");

  let debounceT;

  function fetchJSON(url) {
    return fetch(url, {
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
    }).then(function (r) {
      return r.json();
    });
  }

  function togglePanels() {
    const kind = elKind ? elKind.value : "manual";
    if (panelNova) panelNova.style.display = kind === "nova_poshta" ? "block" : "none";
    if (panelUp) panelUp.style.display = kind === "ukrposhta" ? "block" : "none";
    if (!npConfigured && kind === "nova_poshta" && npHint) {
      npHint.style.display = "block";
    } else if (npHint) {
      npHint.style.display = "none";
    }
  }

  function prefillFromHiddenFieldsIfAny() {
    const kind = elKind ? elKind.value : "";
    if (kind === "nova_poshta") {
      const cityRef = (elNpCityRef && elNpCityRef.value) || "";
      const whRef = (elNpWhRef && elNpWhRef.value) || "";
      const label = (elNpLabel && elNpLabel.value) || "";
      if (whRef && label && npWhPick) {
        // Ensure the select shows the already-chosen branch on page reload
        npWhPick.innerHTML = "";
        const opt0 = document.createElement("option");
        opt0.value = "";
        opt0.textContent = "Select branch…";
        npWhPick.appendChild(opt0);
        const opt = document.createElement("option");
        opt.value = whRef;
        opt.textContent = label;
        opt.selected = true;
        npWhPick.appendChild(opt);
      }
      if (npCitySearch && !npCitySearch.value && cityRef) {
        npCitySearch.value = "Selected city ref: " + cityRef;
      }
    }
    if (kind === "ukrposhta") {
      // Postcode and office line are regular inputs/textarea and should already retain values.
      // If hidden office id exists, keep it as-is; no extra UI needed.
      if (elUpOfficeId && elUpOfficeId.value && elUpLabel && elUpLabel.value) {
        // no-op: just keep existing values visible in textarea
      }
    }
  }

  async function loadCities(q) {
    if (!npConfigured || !q || q.length < 2) return [];
    const data = await fetchJSON(apiNovaCities + "?q=" + encodeURIComponent(q));
    if (!data.success) return [];
    const list = data.data || [];
    return Array.isArray(list) ? list : [];
  }

  async function loadWarehouses(cityRef) {
    if (!npConfigured || !cityRef) return [];
    const data = await fetchJSON(apiNovaWh + "?city_ref=" + encodeURIComponent(cityRef));
    if (!data.success) return [];
    const list = data.data || [];
    return Array.isArray(list) ? list : [];
  }

  function renderCitySuggestions(cities) {
    if (!npCityResults) return;
    npCityResults.innerHTML = "";
    if (!cities.length) {
      npCityResults.style.display = "none";
      return;
    }
    cities.slice(0, 40).forEach(function (c) {
      const ref = c.Ref || c.ref || "";
      const label = (c.Description || c.DescriptionUa || c.DescriptionRu || c.Ref || "").trim();
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "list-group-item list-group-item-action py-2 small text-start";
      btn.dataset.ref = ref;
      btn.textContent = label;
      npCityResults.appendChild(btn);
    });
    npCityResults.style.display = "block";
  }

  function hideCitySuggestions() {
    if (!npCityResults) return;
    npCityResults.innerHTML = "";
    npCityResults.style.display = "none";
  }

  async function selectCity(ref, label) {
    if (elNpCityRef) elNpCityRef.value = ref || "";
    if (npCitySearch) npCitySearch.value = label || "";
    hideCitySuggestions();
    if (elNpWhRef) elNpWhRef.value = "";
    if (elNpLabel) elNpLabel.value = "";
    const whs = await loadWarehouses(ref);
    fillNovaWhPick(whs);
  }

  function fillNovaWhPick(whs) {
    if (!npWhPick) return;
    npWhPick.innerHTML = '<option value="">Select branch…</option>';
    whs.slice(0, 200).forEach(function (w) {
      const opt = document.createElement("option");
      opt.value = w.Ref || "";
      const addr = w.ShortAddress || w.Description || w.DescriptionRu || w.Ref;
      opt.textContent = (addr || "").trim();
      npWhPick.appendChild(opt);
    });
  }

  if (npCitySearch) {
    npCitySearch.addEventListener("input", function () {
      clearTimeout(debounceT);
      debounceT = setTimeout(async function () {
        const q = npCitySearch.value.trim();
        const cities = await loadCities(q);
        if (cities.length === 1) {
          const c = cities[0];
          const ref = c.Ref || c.ref || "";
          const label = (c.Description || c.DescriptionUa || c.DescriptionRu || c.Ref || "").trim();
          await selectCity(ref, label);
          return;
        }
        renderCitySuggestions(cities);
      }, 350);
    });
  }

  if (npCityResults) {
    npCityResults.addEventListener("mousedown", function (e) {
      const btn = e.target.closest("button[data-ref]");
      if (!btn) return;
      e.preventDefault();
      selectCity(btn.dataset.ref, btn.textContent.trim());
    });
  }

  document.addEventListener("click", function (e) {
    if (!npCityResults || !npCitySearch) return;
    if (npCityResults.contains(e.target) || npCitySearch.contains(e.target)) return;
    hideCitySuggestions();
  });

  if (npWhPick) {
    npWhPick.addEventListener("change", function () {
      const opt = npWhPick.selectedOptions[0];
      if (!opt) return;
      if (elNpWhRef) elNpWhRef.value = npWhPick.value;
      if (elNpLabel) elNpLabel.value = opt.textContent || "";
    });
  }

  const btnUpSearch = document.getElementById("pref-btn-up-search");
  const upResults = document.getElementById("pref-up-results");
  if (btnUpSearch && upResults && apiUp && elUpPc) {
    btnUpSearch.addEventListener("click", async function () {
      upResults.innerHTML = '<span class="text-muted">Searching…</span>';
      const data = await fetchJSON(apiUp + "?postcode=" + encodeURIComponent(elUpPc.value.trim()));
      if (!data.success) {
        upResults.innerHTML =
          '<div class="alert alert-warning small">' +
          (data.message || "Configure Ukrposhta API or type the office manually below.") +
          "</div>";
        return;
      }
      const offices = data.offices || data.data || [];
      if (!offices.length) {
        upResults.innerHTML = '<span class="text-muted">No offices returned — type details manually.</span>';
        return;
      }
      upResults.innerHTML = "";
      const sel = document.createElement("select");
      sel.className = "form-select";
      sel.innerHTML = '<option value="">Select office…</option>';
      offices.slice(0, 50).forEach(function (o, idx) {
        const opt = document.createElement("option");
        const id = o.id || o.postofficeId || o.PostOfficeID || String(idx);
        const label = o.name || o.description || o.address || JSON.stringify(o).slice(0, 120);
        opt.value = id;
        opt.textContent = label;
        sel.appendChild(opt);
      });
      sel.addEventListener("change", function () {
        if (elUpOfficeId) elUpOfficeId.value = sel.value;
        if (elUpLabel && sel.selectedOptions[0]) elUpLabel.value = sel.selectedOptions[0].textContent;
      });
      upResults.appendChild(sel);
    });
  }

  if (elKind) elKind.addEventListener("change", togglePanels);

  togglePanels();
  prefillFromHiddenFieldsIfAny();
})();

