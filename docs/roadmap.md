
---

### `docs/ROADMAP.md`
```md
# Roadmap SEOSuite (micro pasos)

## Release 1 (MVP): Google First Keyword Research + Activation mínima
Objetivo: tener Keyword Research usable con trazabilidad run-based y gates.

1. Projects
- Guardar: `gsc_property`, `ga4_property_id`, `ads_customer_id` (Ads obligatorio)
- UI: crear/editar proyecto

2. Integrations: “Test access”
- Botones: Test GSC, Test GA4, Test Ads
- Persistir resultado por proyecto (OK/FAIL + raw response)

3. Keyword Overview
- Entrada: keyword + locale/language/geo
- Salida: Keyword Metrics Contract canónico (source=Google Ads)

4. Keyword Magic Tool
- Entrada: seed keyword
- Salida: ideas + métricas (contract) + filtros básicos

5. Export PDF (snapshots)
- Exportar resultados desde snapshots/run outputs

## Release 2: SERP Provider + Position Tracking + Keyword Gap
Gate: SERP provider configurado.

- Position Tracking (runs recurrentes + snapshots)
- Keyword Gap (missing/weak vs competidores)
- Enriquecimiento opcional (DataForSEO) como fallback/enrichment

## Release 3: Site Audit + Insights
- Crawler + checks técnicos
- Insights accionables (priorización)
