from django.db.models import Q
from django.shortcuts import render

from projects.models import Project
from serp.models import SerpRun, SerpKeywordSnapshot


def rankings(request):
    project_id = request.GET.get("project") or ""
    q = (request.GET.get("q") or "").strip()

    projects = Project.objects.select_related("client").order_by("client__name", "name")

    latest_run = None
    prev_run = None
    rows = []

    if project_id:
        runs = list(
            SerpRun.objects.filter(project_id=project_id, status=SerpRun.Status.DONE)
            .order_by("-created_at")[:2]
        )
        if len(runs) >= 1:
            latest_run = runs[0]
        if len(runs) >= 2:
            prev_run = runs[1]

    if latest_run:
        latest_qs = SerpKeywordSnapshot.objects.filter(serp_run=latest_run).select_related("keyword")
        if q:
            latest_qs = latest_qs.filter(Q(keyword__keyword__icontains=q))

        prev_map = {}
        if prev_run:
            prev_qs = (
                SerpKeywordSnapshot.objects.filter(serp_run=prev_run)
                .only("keyword_id", "tracked_position", "top_domain", "top_url", "top3_domains", "top3_urls")
            )
            prev_map = {
                s.keyword_id: {
                    "tracked_position": s.tracked_position,
                    "top_domain": s.top_domain or "",
                    "top_url": s.top_url or "",
                    "top3_domains": s.top3_domains or [],
                    "top3_urls": s.top3_urls or [],
                }
                for s in prev_qs
            }

        for s in latest_qs.order_by("keyword__keyword"):
            prev_data = prev_map.get(s.keyword_id) or {}
            prev_pos = prev_data.get("tracked_position")

            prev_top_domain = prev_data.get("top_domain") or ""
            prev_top_url = prev_data.get("top_url") or ""

            cur_pos = s.tracked_position

            # Movement for tracked domain
            if prev_pos is None and cur_pos is None:
                movement = "No rank"
            elif prev_pos is None and cur_pos is not None:
                movement = "New"
            elif prev_pos is not None and cur_pos is None:
                movement = "Lost"
            else:
                delta = prev_pos - cur_pos
                if delta > 0:
                    movement = f"Up {delta}"
                elif delta < 0:
                    movement = f"Down {abs(delta)}"
                else:
                    movement = "No change"

            # Top1 (SERP) change
            cur_top_domain = s.top_domain or ""
            cur_top_url = s.top_url or ""

            if not prev_run:
                serp_change_label = "-"
            else:
                serp_top1_changed = (prev_top_domain != cur_top_domain) or (prev_top_url != cur_top_url)
                serp_change_label = "Changed" if serp_top1_changed else "Same"

            # ---- Paso 3: Top3 volatility (esto te faltaba) ----
            prev_top3_domains = prev_data.get("top3_domains") or []
            prev_top3_urls = prev_data.get("top3_urls") or []

            cur_top3_domains = s.top3_domains or []
            cur_top3_urls = s.top3_urls or []

            def _pad3(lst):
                lst = lst or []
                return (lst + ["", "", ""])[:3]

            prev3 = _pad3(prev_top3_domains)
            cur3 = _pad3(cur_top3_domains)

            if not prev_run:
                top3_score = None
            else:
                top3_score = sum(1 for i in range(3) if prev3[i] != cur3[i])


            if not prev_run:
                top3_label = "-"
            else:
                top3_changed = (prev_top3_domains != cur_top3_domains) or (prev_top3_urls != cur_top3_urls)
                top3_label = "Changed" if top3_changed else "Same"
            # ---------------------------------------------------

            rows.append(
                {
                    "keyword": s.keyword.keyword,
                    "current": cur_pos,
                    "previous": prev_pos,
                    "movement": movement,
                    "serp_top1": serp_change_label,
                    "prev_top_domain": prev_top_domain,
                    "prev_top_url": prev_top_url,
                    "cur_top_domain": cur_top_domain,
                    "cur_top_url": cur_top_url,
                    "top_domain": cur_top_domain,
                    "top_position": s.top_position,
                    "top3_volatility": top3_label,
                    "prev_top3_domains": prev_top3_domains,
                    "cur_top3_domains": cur_top3_domains,
                    "prev_top3_urls": prev_top3_urls,
                    "cur_top3_urls": cur_top3_urls,
                    "top3_score": top3_score,
                }
            )

    return render(
        request,
        "core/rankings.html",
        {
            "projects": projects,
            "project_id": project_id,
            "q": q,
            "latest_run": latest_run,
            "prev_run": prev_run,
            "rows": rows,
        },
    )
