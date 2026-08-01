"""Generate the Evaluation screen prototype from the committed evaluation artifacts.

The prototype is a single self-contained page. Its numbers are embedded at build time
from `eval/results/*.json`, so the screen and the README cannot drift apart: regenerating
it is the only way its contents change.

    python scripts/build_eval_prototype.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
OUT = ROOT / "apps" / "web" / "prototype" / "evaluation.html"

LABELS = {
    "dense": "dense",
    "mmr": "MMR, lambda 0.5",
    "lexical": "lexical, Postgres FTS",
    "rrf": "RRF fusion, k=60",
    "rrf_expansion": "RRF fusion + expansion",
    "rrf_rerank": "RRF fusion + cross-encoder",
}
ORDER = list(LABELS)
CHUNKINGS = ["recursive-512", "recursive-1024", "clause-aware"]

TEMPLATE = """<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ChainLens evaluation</title>
<style>
{tokens}
</style>
<style>
/* Prototype-only layout. Every colour, size, space and duration below resolves to a
   semantic token from tokens.css. There is no raw hex in this file. */
*, *::before, *::after {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--ground);
  color: var(--ink);
  font-family: var(--font-ui, ui-sans-serif, system-ui, sans-serif);
  font-size: 0.9375rem;
  line-height: 1.35;
}}
.masthead {{
  display: flex; align-items: baseline; gap: 1rem;
  padding: 1rem 1.5rem;
  border-bottom: 2px solid var(--ink);
}}
h1 {{ font-size: 0.9375rem; font-weight: 620; margin: 0; letter-spacing: 0.01em; }}
.masthead .stamp {{
  font-family: var(--font-identity, ui-monospace, monospace);
  font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--accent); border: 1px solid var(--accent);
  padding: 2px 6px; border-radius: var(--radius-chip, 3px);
}}
.masthead .spacer {{ margin-left: auto; }}
button.toggle {{
  font: inherit; font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--ink-muted); background: transparent;
  border: 1px solid var(--rule-control); border-radius: var(--radius-field, 2px);
  min-height: 32px; padding: 0 0.75rem; cursor: pointer;
  transition: background-color var(--duration-hover, 120ms) var(--ease-enter, ease-out),
              border-color var(--duration-hover, 120ms) var(--ease-enter, ease-out),
              transform var(--duration-hover, 120ms) var(--ease-enter, ease-out);
}}
button.toggle:hover {{ background: var(--panel-raised); border-color: var(--ink-muted); }}
button.toggle:active {{ transform: translateY(1px); }}
main {{ padding: 1.5rem; max-width: 1440px; }}
.field-label {{
  font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--ink-faint); font-family: var(--font-ui, sans-serif);
}}
.figures {{ display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 1.5rem; }}
.figure {{
  border: 1px solid var(--rule); border-top: 2px solid var(--ink);
  background: var(--panel); padding: 0.75rem 1rem; min-width: 13rem;
}}
.figure .value {{
  font-family: var(--font-identity, ui-monospace, monospace);
  font-variant-numeric: tabular-nums;
  font-size: 1.5rem; margin-top: 0.25rem; display: block;
}}
.figure .note {{ font-size: 0.8125rem; color: var(--ink-muted); margin-top: 0.25rem; }}
.table-wrap {{ overflow-x: auto; border: 1px solid var(--rule); background: var(--panel); }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.8125rem; }}
caption {{
  text-align: left; padding: 0.75rem 1rem; color: var(--ink-muted);
  border-bottom: 1px solid var(--rule); font-size: 0.8125rem;
}}
th, td {{ padding: 0.5rem 0.75rem; text-align: right; border-bottom: 1px solid var(--rule); }}
th[scope="col"] {{
  font-weight: 620; font-size: 0.6875rem; text-transform: uppercase;
  letter-spacing: 0.08em; color: var(--ink-faint); white-space: nowrap;
  border-bottom: 2px solid var(--ink);
}}
th[scope="row"], td.label {{ text-align: left; font-weight: 380; white-space: nowrap; }}
td.num {{
  font-family: var(--font-identity, ui-monospace, monospace);
  font-variant-numeric: tabular-nums;
}}
tbody tr {{
  transition: background-color var(--duration-hover, 120ms) var(--ease-enter, ease-out);
}}
tbody tr:hover {{ background: var(--panel-raised); }}
tbody tr.best td.num.lead {{ color: var(--accent); font-weight: 600; }}
tbody tr.blocked td {{ color: var(--ink-faint); }}
tbody tr.group th {{
  text-align: left; padding-top: 1rem;
  font-family: var(--font-identity, ui-monospace, monospace);
  font-size: 0.6875rem; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--ink-faint); border-bottom: 1px solid var(--rule-control);
}}
.footnote {{ margin-top: 0.75rem; font-size: 0.8125rem; color: var(--ink-muted); max-width: 70ch; }}
.provenance {{
  margin-top: 1.5rem; padding-top: 0.75rem; border-top: 1px solid var(--rule);
  font-size: 0.8125rem; color: var(--ink-muted); max-width: 80ch;
}}
.provenance code, .mono {{
  font-family: var(--font-identity, ui-monospace, monospace); font-size: 0.8125rem;
}}
.empty {{
  border: 1px dashed var(--rule-control); padding: 1.5rem; color: var(--ink-muted);
}}
</style>
</head>
<body>
<header class="masthead">
  <h1>ChainLens</h1>
  <span class="stamp">Evaluation</span>
  <span class="spacer"></span>
  <button class="toggle" id="theme" aria-pressed="false">Dark</button>
</header>
<main>
  <section class="figures" aria-label="Headline measurements">
    {figures}
  </section>

  <div class="table-wrap">
  <table>
    <caption>{caption}</caption>
    <thead>
      <tr>
        <th scope="col">retrieval</th>
        <th scope="col">Recall@3</th>
        <th scope="col">Recall@6</th>
        <th scope="col">Recall@10</th>
        <th scope="col">MRR</th>
        <th scope="col">nDCG@10</th>
        <th scope="col">hit@6</th>
        <th scope="col">answer chars @6</th>
        <th scope="col">p50 ms</th>
        <th scope="col">p95 ms</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
  </div>
  <p class="footnote">{footnote}</p>
  <div class="provenance">{provenance}</div>
</main>
<script>
  const button = document.getElementById("theme");
  button.addEventListener("click", () => {{
    const root = document.documentElement;
    const dark = root.dataset.theme === "dark";
    root.dataset.theme = dark ? "light" : "dark";
    button.textContent = dark ? "Dark" : "Light";
    button.setAttribute("aria-pressed", String(!dark));
  }});
</script>
</body>
</html>
"""


def load() -> dict[str, dict[str, object]]:
    """Retrieval runs only.

    eval/results/ also holds the extraction evaluation, which has a different metric set.
    Selecting on the presence of recall@6 rather than on the filename means a new
    retrieval run is picked up automatically and a new kind of run is not mistaken for one.
    """
    results: dict[str, dict[str, object]] = {}
    for path in sorted(RESULTS.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        metrics = payload.get("metrics") or {}
        is_retrieval = "recall@6" in metrics or payload.get("status") != "ok"
        if not is_retrieval or "config" not in payload:
            continue
        payload.pop("per_query", None)
        results[str(payload["run_id"])] = payload
    return results


def cell(result: dict[str, object] | None, key: str, digits: int = 3, lead: bool = False) -> str:
    classes = "num lead" if lead else "num"
    if result is None or result.get("status") != "ok":
        return f'<td class="{classes}">--</td>'
    metrics = result["metrics"]
    value = metrics.get(key) if isinstance(metrics, dict) else None
    if value is None:
        return f'<td class="{classes}">--</td>'
    return f'<td class="{classes}">{float(value):.{digits}f}</td>'


def read_tokens() -> str:
    """Inline the token layer.

    The prototype is meant to open by double-clicking it, which rules out a stylesheet
    link with a relative path and rules out the Tailwind @import. Only the plain-CSS parts
    are inlined; the @import line is dropped because a browser opening this from disk has
    nothing to resolve it against.
    """
    source = (ROOT / "apps" / "web" / "app" / "tokens.css").read_text(encoding="utf-8")
    return "\n".join(line for line in source.splitlines() if not line.strip().startswith("@import"))


def build() -> str:
    results = load()
    ok = [item for item in results.values() if item.get("status") == "ok"]
    tokens = read_tokens()
    if not ok:
        return TEMPLATE.format(
            tokens=tokens,
            figures='<div class="empty">No evaluation runs are present in '
            'eval/results/. Run <span class="mono">python -m eval.run</span> to '
            "produce them, then regenerate this page.</div>",
            caption="No results",
            rows="",
            footnote="",
            provenance="",
        )

    sample = ok[0]
    best = max(ok, key=lambda item: float(item["metrics"]["recall@6"]))  # type: ignore[index]
    best_metrics = best["metrics"]
    assert isinstance(best_metrics, dict)

    embed_share = float(best_metrics["embed_ms_p50"]) / float(best_metrics["latency_ms_p50"])
    figures = "".join(
        f'<div class="figure"><span class="field-label">{label}</span>'
        f'<span class="value">{value}</span>'
        f'<span class="note">{note}</span></div>'
        for label, value, note in [
            (
                "Best Recall@6",
                f"{float(best_metrics['recall@6']):.3f}",
                f"{best['run_id']}",
            ),
            (
                "Query embedding share of latency",
                f"{100 * embed_share:.0f}%",
                f"{best_metrics['embed_ms_p50']} ms of {best_metrics['latency_ms_p50']} ms at p50",
            ),
            (
                "Postgres search p50",
                f"{best_metrics['search_ms_p50']} ms",
                "dense plus lexical, both arms",
            ),
            (
                "Questions scored",
                str(best_metrics["n_evaluated"]),
                f"{sample['dataset']['documents']} documents, "  # type: ignore[index]
                f"{sample['dataset']['categories']} clause categories",  # type: ignore[index]
            ),
        ]
    )

    rows: list[str] = []
    for chunking in CHUNKINGS:
        rows.append(
            f'      <tr class="group"><th scope="rowgroup" colspan="10">'
            f"chunking: {chunking}</th></tr>"
        )
        for key in ORDER:
            result = results.get(f"{chunking}__{key}")
            blocked = result is None or result.get("status") != "ok"
            is_best = result is not None and result.get("run_id") == best["run_id"]
            classes = " ".join(
                filter(None, ["blocked" if blocked else "", "best" if is_best else ""])
            )
            attribute = f' class="{classes}"' if classes else ""
            rows.append(
                f"      <tr{attribute}>"
                f'<th scope="row">{LABELS[key]}</th>'
                + cell(result, "recall@3")
                + cell(result, "recall@6", lead=True)
                + cell(result, "recall@10")
                + cell(result, "mrr")
                + cell(result, "ndcg@10")
                + cell(result, "hit@6")
                + cell(result, "span_coverage@6")
                + cell(result, "latency_ms_p50", 1)
                + cell(result, "latency_ms_p95", 1)
                + "</tr>"
            )

    reasons = {
        str(item.get("blocked_reason")) for item in results.values() if item.get("status") != "ok"
    }
    footnote = (
        "Cells marked -- were not measured. " + " ".join(sorted(reasons))
        if reasons
        else "Every cell in this table was measured."
    )

    dataset = sample["dataset"]
    environment = sample["environment"]
    assert isinstance(dataset, dict) and isinstance(environment, dict)
    embedding = environment["embedding"]
    assert isinstance(embedding, dict)
    provenance = (
        f"Generated from {len(results)} artifacts in eval/results/ at commit "
        f"<code>{str(sample['git_sha'])[:12]}</code> on {sample['created_at']}. "
        f"Dataset <code>{dataset['path']}</code>, sha256 "
        f"<code>{str(dataset['sha256'])[:16]}</code>. Embedding provider "
        f"<code>{embedding['provider']}</code>, dimension {embedding['dim']}. "
        f"Postgres {environment['postgres']}. Retrieval is scoped to the document the "
        "question is about. The embedding provider is not bge-small-en-v1.5: the model "
        "hub was unreachable when these numbers were produced, so these values are a "
        "floor for the architecture rather than a claim about a modern encoder. "
        "See ADR-0003."
    )
    caption = (
        f"Retrieval ablation, {dataset['items']} questions over "
        f"{dataset['documents']} supply-chain contracts. Recall@6 leads because it is "
        "the column the configuration decision turned on."
    )
    return TEMPLATE.format(
        tokens=tokens,
        figures=figures,
        caption=caption,
        rows="\n".join(rows),
        footnote=footnote,
        provenance=provenance,
    )


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
