/**
 * Ukraine delivery: Nova Poshta (API) + optional Ukrposhta manual/API.
 * City: one search field + clickable suggestions (no second city dropdown).
 */
(function () {
  const root = document.getElementById("delivery-ua-root");
  if (!root) return;

  const apiNovaCities = root.dataset.apiNovaCities;
  const apiNovaWh = root.dataset.apiNovaWarehouses;
  const apiUp = root.dataset.apiUp;
  const npConfigured = root.dataset.novaConfigured === "1";

  const elCountry = document.getElementById("id_delivery_country");
  const elKind = document.getElementById("id_delivery_kind");
  const elNpCityRef = document.getElementById("id_np_city_ref");
  const elNpWhRef = document.getElementById("id_np_warehouse_ref");
  const elNpLabel = document.getElementById("id_np_label");
  const elUpPc = document.getElementById("id_up_postcode");
  const elUpOfficeId = document.getElementById("id_up_office_id");
  const elUpLabel = document.getElementById("id_up_label");

  const panelUa = document.getElementById("panel-ua-carriers");
  const panelOther = document.getElementById("panel-other-only");
  const panelNova = document.getElementById("panel-nova");
  const panelUp = document.getElementById("panel-ukrposhta");

  const npCitySearch = document.getElementById("np-city-search");
  const npCityResults = document.getElementById("np-city-results");
  const npWhPick = document.getElementById("np-wh-pick");
  const npHint = document.getElementById("np-api-hint");

  let debounceT;

  function togglePanels() {
    const ua = elCountry && elCountry.value === "UA";
    if (panelUa) panelUa.style.display = ua ? "block" : "none";
    if (panelOther) panelOther.style.display = ua ? "none" : "block";
    if (!ua && elKind) {
      elKind.value = "manual";
      elKind.disabled = true;
    }
    if (ua && elKind) elKind.disabled = false;

    const kind = elKind ? elKind.value : "manual";
    if (panelNova) panelNova.style.display = ua && kind === "nova_poshta" ? "block" : "none";
    if (panelUp) panelUp.style.display = ua && kind === "ukrposhta" ? "block" : "none";

    if (!npConfigured && kind === "nova_poshta" && npHint) {
      npHint.style.display = "block";
    } else if (npHint) npHint.style.display = "none";
  }

  async function fetchJSON(url) {
    const r = await fetch(url, {
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest", Accept: "application/json" },
    });
    return r.json();
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
    npWhPick.innerHTML = '<option value="">Select warehouse…</option>';
    whs.slice(0, 200).forEach(function (w) {
      const opt = document.createElement("option");
      opt.value = w.Ref || "";
      const addr = w.ShortAddress || w.Description || w.DescriptionRu || w.Ref;
      opt.textContent = (addr || "").trim();
      opt.dataset.lat = w.Latitude || w.latitude || "";
      opt.dataset.lng = w.Longitude || w.longitude || "";
      npWhPick.appendChild(opt);
    });
  }

  function prefillFromHiddenFieldsIfAny() {
    // When create-request is opened with initial values, the hidden NP fields
    // are already set, but the visible <select> doesn't know them yet.
    const kind = elKind ? elKind.value : "";
    if (kind !== "nova_poshta") return;
    const cityRef = (elNpCityRef && elNpCityRef.value) || "";
    const whRef = (elNpWhRef && elNpWhRef.value) || "";
    const label = (elNpLabel && elNpLabel.value) || "";
    if (!cityRef || !whRef || !label) return;
    if (!npWhPick) return;
    // Insert the current choice so the user sees it immediately.
    npWhPick.innerHTML = "";
    const opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = "Select warehouse…";
    npWhPick.appendChild(opt0);
    const opt = document.createElement("option");
    opt.value = whRef;
    opt.textContent = label;
    opt.selected = true;
    npWhPick.appendChild(opt);
    if (npCitySearch && !npCitySearch.value) {
      npCitySearch.value = "Selected city ref: " + cityRef;
    }
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
      const txt = opt.textContent || "";
      if (elNpLabel) elNpLabel.value = txt;
    });
  }

  if (elCountry) elCountry.addEventListener("change", togglePanels);
  if (elKind) elKind.addEventListener("change", togglePanels);

  const btnUpSearch = document.getElementById("btn-up-search");
  const upResults = document.getElementById("up-results");
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
        elUpOfficeId.value = sel.value;
        elUpLabel.value = sel.selectedOptions[0] ? sel.selectedOptions[0].textContent : "";
      });
      upResults.appendChild(sel);
    });
  }

  document.querySelector("form")?.addEventListener("submit", function () {
    if (elCountry && elCountry.value !== "UA") {
      if (elNpCityRef) elNpCityRef.value = "";
      if (elNpWhRef) elNpWhRef.value = "";
      if (elNpLabel) elNpLabel.value = "";
      if (elUpOfficeId) elUpOfficeId.value = "";
    }
    if (elKind && elKind.value !== "nova_poshta") {
      if (elNpCityRef) elNpCityRef.value = "";
      if (elNpWhRef) elNpWhRef.value = "";
      if (elNpLabel) elNpLabel.value = "";
    }
    if (elKind && elKind.value !== "ukrposhta") {
      if (elUpOfficeId) elUpOfficeId.value = "";
      if (elUpPc) elUpPc.value = "";
    }
  });

  togglePanels();
  prefillFromHiddenFieldsIfAny();
})();
