// clients/static/clients/admin/client_chained_geo.js
document.addEventListener("DOMContentLoaded", () => {
    // 1) Encontrar selects de forma tolerante (id o name)
    const countryEl =
        document.getElementById("id_country") ||
        document.querySelector('select[name$="country"]');

    const regionEl =
        document.getElementById("id_region") ||
        document.querySelector('select[name$="region"]');

    const cityEl =
        document.getElementById("id_city") ||
        document.querySelector('select[name$="city"]');

    if (!countryEl || !regionEl || !cityEl) return;

    // 2) Limpiar ids raros como "<1>"
    const cleanId = (v) => {
        const m = String(v || "").match(/\d+/);
        return m ? m[0] : "";
    };

    // 3) Fallback URL builder: /admin/clients/client/ + ajax/regions/
    function adminBasePath() {
        // Ej: /admin/clients/client/add/  o /admin/clients/client/12/change/
        let p = window.location.pathname;
        p = p.replace(/add\/$/, "");
        p = p.replace(/\d+\/change\/$/, "");
        if (!p.endsWith("/")) p += "/";
        return p;
    }

    const base = adminBasePath();
    const regionsUrl = regionEl.getAttribute("data-ajax-url") || (base + "ajax/regions/");
    const citiesUrl = cityEl.getAttribute("data-ajax-url") || (base + "ajax/cities/");

    function setOptions(selectEl, items) {
        selectEl.innerHTML = "";
        const emptyOpt = document.createElement("option");
        emptyOpt.value = "";
        emptyOpt.textContent = "---------";
        selectEl.appendChild(emptyOpt);

        for (const it of items) {
            const opt = document.createElement("option");
            opt.value = String(it.id);
            opt.textContent = it.name;
            selectEl.appendChild(opt);
        }
    }

    async function fetchJSON(url, params) {
        const qs = new URLSearchParams(params);
        const resp = await fetch(`${url}?${qs.toString()}`, {
            method: "GET",
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        });
        if (!resp.ok) return [];
        return await resp.json();
    }

    async function loadRegions() {
        const countryId = cleanId(countryEl.value);
        setOptions(regionEl, []);
        setOptions(cityEl, []);

        if (!countryId) return;

        const items = await fetchJSON(regionsUrl, { country: countryId });
        setOptions(regionEl, items);
    }

    async function loadCities() {
        const regionId = cleanId(regionEl.value);
        setOptions(cityEl, []);

        if (!regionId) return;

        const items = await fetchJSON(citiesUrl, { region: regionId });
        setOptions(cityEl, items);
    }

    countryEl.addEventListener("change", loadRegions);
    regionEl.addEventListener("change", loadCities);

    // Carga inicial (si ya hay país seleccionado)
    if (cleanId(countryEl.value)) loadRegions();
});
