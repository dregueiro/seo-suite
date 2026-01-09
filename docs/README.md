# SEOSuite

Plataforma SEO tipo Semrush enfocada en costo, trazabilidad y ejecución (run-based).
**Principio rector:** Google First (GSC + GA4 + Ads), SERP providers solo cuando aplica (SerpAPI / DataForSEO).

## Estado actual
- Repositorio: implementación en curso (Release 1: Keyword Research + Activation mínima)
- Documentación base: ver `/docs/`

## Arquitectura (obligatoria)
Apps por dominio (no por proveedor):
- core, clients, projects, integrations, keyword_research, serp, insights, audit, jobs, seo
Reglas:
- `seo` solo orquesta navegación y presentación, sin lógica de proveedores.
- Todo proveedor se integra en `integrations/` y mapea a contratos canónicos.

## Concepto Run-based (no negociable)
Cada operación crea un **Run** con:
- inputs, outputs, raw_response (auditoría), costo estimado/real, estado, timestamps
- cache con claves determinísticas + dedupe fuerte (no pagar 2 veces)

## Sistema Operativo SEO (Semrush-like)
Este es el flujo operativo que guía features y releases:

1) **Descubrimiento (Keyword Magic Tool)**
- Expande universo de keywords desde “seed/head keyword”
- Filtros (preguntas, intent, etc.) y agrupación (clustering)

2) **Inteligencia competitiva (Keyword Gap)**
- Missing/Weak vs competidores
- Priorización por dificultad (KD) y oportunidad

3) **Ejecución On-Page (Site Audit)**
- Checklist técnico y on-page
- Validar que el sitio “sea digno” de rankear

4) **Seguimiento (Position Tracking)**
- Tracking recurrente por keyword/locale/device
- Revisión semanal/mensual y ajustes

## Gates (bloqueos obligatorios)
- **Keyword Research** requiere Google Ads configurado y acceso OK (`ads_customer_id` + permisos). Si no está OK, se bloquea.
- **Keyword Gap** y **Position Tracking** requieren proveedor SERP configurado (SerpAPI o DataForSEO).

## Quickstart (local)
```bash
python -m venv .venv
source .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
