(function () {
    function getBaseUrl() {
        // /admin/clients/client/add/  -> /admin/clients/client/
        // /admin/clients/client/1/change/ -> /admin/clients/client/
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
        if (selectedValue) {
            selectEl.value = String(selectedValue);
        }
    }

    async function fetchJson(url) {
        const res = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
        if (!res.ok) return [];
        return await res.json();
    }

    async function loadRegions({ baseUrl, countryId, regionSelect, selectedRegionId }) {
        if (!countryId) {
            clearSelect(regionSelect, "---------");
            return;
        }
        const url = `${baseUrl}ajax/regions/?country=${encodeURIComponent(countryId)}`;
        const data = await fetchJson(url);
        fillSelect(regionSelect, data, selectedRegionId, "---------");
    }

    async function loadCities({ baseUrl, regionId, citySelect, selectedCityId }) {
        if (!regionId) {
            clearSelect(citySelect, "---------");
            return;
        }
        const url = `${baseUrl}ajax/cities/?region=${encodeURIComponent(regionId)}`;
        const data = await fetchJson(url);
        fillSelect(citySelect, data, selectedCityId, "---------");
    }

    document.addEventListener("DOMContentLoaded", async function () {
        const country = document.getElementById("id_country");
        const region = document.getElementById("id_region");
        const city = document.getElementById("id_city");
        if (!country || !region || !city) return;

        const baseUrl = getBaseUrl();

        // Guardar selección actual (lo que viene de DB en change form)
        const savedRegionId = region.value || "";
        const savedCityId = city.value || "";

        // 1) Cargar regiones según country y restaurar región guardada
        await loadRegions({
            baseUrl,
            countryId: country.value,
            regionSelect: region,
            selectedRegionId: savedRegionId,
        });

        // 2) Cargar ciudades según región (ya restaurada) y restaurar ciudad guardada
        await loadCities({
            baseUrl,
            regionId: region.value,
            citySelect: city,
            selectedCityId: savedCityId,
        });

        // Events
        country.addEventListener("change", async function () {
            // Al cambiar country, recargar regiones y limpiar ciudades
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
