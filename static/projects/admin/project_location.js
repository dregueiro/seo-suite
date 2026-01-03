(function () {
    function getBaseUrl() {
        // /admin/projects/project/add/        -> /admin/projects/project/
        // /admin/projects/project/1/change/   -> /admin/projects/project/
        const p = window.location.pathname;
        if (p.endsWith("/add/")) return p.replace(/add\/$/, "");
        if (p.endsWith("/change/")) return p.replace(/\/\d+\/change\/$/, "/");
        return p;
    }

    function clearSelect(selectEl, placeholder) {
        selectEl.innerHTML = "";
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = placeholder || "---------";
        selectEl.appendChild(opt);
    }

    function fillSelect(selectEl, items, selectedValue, placeholder) {
        clearSelect(selectEl, placeholder);
        for (const it of items) {
            const opt = document.createElement("option");
            opt.value = String(it.id);
            opt.textContent = it.name;
            selectEl.appendChild(opt);
        }
        if (selectedValue) selectEl.value = String(selectedValue);
    }

    async function fetchJson(url, fallback) {
        const res = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
        if (!res.ok) return fallback;
        return await res.json();
    }

    async function loadRegions({ baseUrl, countryId, regionSelect, selectedRegionId }) {
        if (!countryId) {
            clearSelect(regionSelect, "---------");
            return;
        }
        const url = `${baseUrl}ajax/regions/?country=${encodeURIComponent(countryId)}`;
        const data = await fetchJson(url, []);
        fillSelect(regionSelect, data, selectedRegionId, "---------");
    }

    async function loadCities({ baseUrl, regionId, citySelect, selectedCityId }) {
        if (!regionId) {
            clearSelect(citySelect, "---------");
            return;
        }
        const url = `${baseUrl}ajax/cities/?region=${encodeURIComponent(regionId)}`;
        const data = await fetchJson(url, []);
        fillSelect(citySelect, data, selectedCityId, "---------");
    }

    async function loadClientDefaults({ baseUrl, clientId }) {
        if (!clientId) return { country: "", region: "", city: "" };
        const url = `${baseUrl}ajax/client-defaults/?client=${encodeURIComponent(clientId)}`;
        return await fetchJson(url, { country: "", region: "", city: "" });
    }

    document.addEventListener("DOMContentLoaded", async function () {
        const client = document.getElementById("id_client");
        const country = document.getElementById("id_country");
        const region = document.getElementById("id_region");
        const city = document.getElementById("id_city");

        if (!client || !country || !region || !city) return;

        const baseUrl = getBaseUrl();

        // Estado inicial (change form)
        const savedRegionId = region.value || "";
        const savedCityId = city.value || "";

        // 1) Cargar regiones/cities iniciales según lo que ya venga seteado
        await loadRegions({
            baseUrl,
            countryId: country.value,
            regionSelect: region,
            selectedRegionId: savedRegionId,
        });

        await loadCities({
            baseUrl,
            regionId: region.value,
            citySelect: city,
            selectedCityId: savedCityId,
        });

        // 2) Cuando cambia client: aplicar defaults del client + recargar dependientes
        client.addEventListener("change", async function () {
            const defaults = await loadClientDefaults({ baseUrl, clientId: client.value });

            country.value = defaults.country ? String(defaults.country) : "";
            await loadRegions({
                baseUrl,
                countryId: country.value,
                regionSelect: region,
                selectedRegionId: defaults.region ? String(defaults.region) : "",
            });

            await loadCities({
                baseUrl,
                regionId: region.value,
                citySelect: city,
                selectedCityId: defaults.city ? String(defaults.city) : "",
            });
        });

        // 3) Dependientes manuales
        country.addEventListener("change", async function () {
            await loadRegions({
                baseUrl,
                countryId: country.value,
                regionSelect: region,
                selectedRegionId: "",
            });
            clearSelect(city, "---------");
        });

        region.addEventListener("change", async function () {
            await loadCities({
                baseUrl,
                regionId: region.value,
                citySelect: city,
                selectedCityId: "",
            });
        });
    });
})();
