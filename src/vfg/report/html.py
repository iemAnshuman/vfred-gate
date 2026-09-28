"""Network-free HTML rebuilt from verified raw evidence."""

from pathlib import Path
from jinja2 import Environment, select_autoescape
from ..controller import rederive
from ..manifest import load_document, now

TEMPLATE = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>VFRED-Gate {{ verdict.verdict }} — {{ inputs.plan.id }}</title>
<style>body{font:16px/1.55 system-ui;max-width:1150px;margin:3rem auto;padding:0 1.5rem;color:#17212b;background:#f6f8fa}h1,h2{line-height:1.2}section{background:white;padding:1.5rem;margin:1rem 0;border:1px solid #d0d7de;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:.55rem;border-bottom:1px solid #ddd;vertical-align:top}code,pre{font:13px/1.5 ui-monospace,monospace;overflow-wrap:anywhere;white-space:pre-wrap}.badge{font-size:1.5rem;font-weight:700;color:{{ color }}}a{color:#0969da}.muted{color:#57606a}</style>
<h1>VFRED-Gate qualification</h1><p class="badge">{{ verdict.verdict }}</p><p>{{ inputs.plan.id }} · {{ verdict.evidence.execution_class }} · {{ verdict.evidence.distinct_cases }} distinct cases · {{ verdict.evidence.completed_jobs }} completed executions</p>
<section><h2>Scope and evidence</h2><p>Contract: <strong>{{ inputs.contract.id }}</strong>. Legality: <strong>not assessed</strong>. {% if verdict.evidence.diagnostic_injection %}<strong>This is an injected diagnostic validation. It is not a natural compiler discrepancy.</strong>{% else %}This result describes only the recorded stacks, corpus and settings.{% endif %}</p><p>RVV hardware qualification, legal-tree replay, canary prediction and hardening are outside this run.</p><p>Actual execution: {{ run.started_at }} to {{ run.finished_at }}. Report reconstructed offline: {{ rendered }}.</p><p>Bundle SHA-256: <code>{{ sha }}</code></p><ul>{% for reason in verdict.reasons %}<li>{{ reason }}</li>{% endfor %}</ul></section>
<section><h2>Contract rules</h2><table><tr><th>Rule</th><th>Alignment</th><th>Value / threshold</th><th>Denominator</th><th>Result</th></tr>{% for rule in verdict.rules %}<tr><td>{{ rule.id }}<br>{{ rule.metric }}</td><td>{{ rule.alignment }}</td><td>{{ rule.value }} {{ rule.operator }} {{ rule.threshold }}</td><td>{{ rule.denominator }}</td><td>{{ 'PASS' if rule.passed else 'FAIL' }}</td></tr>{% endfor %}</table><p>Free-running numeric comparisons stop after the first differing choice. Teacher-forced comparisons use the same baseline continuation. Repetitions establish stability and do not increase the independent case count.</p></section>
<section><h2>First sequence divergence</h2><table><tr><th>Case</th><th>Position</th><th>Observed baseline steps</th></tr>{% for item in divergences %}<tr><td>{{ item.case_id }}</td><td>{{ 'none observed (censored)' if item.censored else item.position }}</td><td>{{ item.observed_steps }}</td></tr>{% endfor %}</table></section>
<section><h2>Identities and controls</h2><table><tr><th></th><th>Baseline</th><th>Candidate</th></tr>{% for field in ['id','binary_sha256','source_revision','source_digest','build_class','reduction_policy','compiler','flags','injection'] %}<tr><th>{{ field }}</th><td><code>{{ inputs.baseline[field] }}</code></td><td><code>{{ inputs.candidate[field] }}</code></td></tr>{% endfor %}</table><p>Model: <code>{{ inputs.model.sha256 }}</code></p><pre>{{ inputs.plan.settings }}</pre><pre>{{ verdict.evidence.manifest_diff }}</pre></section>
<section><h2>Stability and margins</h2><p>{{ stable }} / {{ verdict.evidence.stability|length }} case/stack/mode groups satisfy all requested bitwise repetitions.</p><table><tr><th>Case</th><th>Minimum top-two margin</th><th>Mean margin</th></tr>{% for case,item in margins.items() %}<tr><td>{{ case }}</td><td>{{ item.minimum }}</td><td>{{ item.mean }}</td></tr>{% endfor %}</table><p>Margins are descriptive. No held-out failure prediction has been evaluated.</p></section>
{% if localisation %}<section><h2>Injected diagnostic localisation</h2><p>Case {{ localisation.case_id }}, step {{ localisation.prediction_step }}. Earliest differing tensor <strong>{{ localisation.earliest_difference.name }}</strong>, operator <strong>{{ localisation.earliest_difference.op }}</strong>.</p><p>Matching histories: {{ localisation.history_matched }}. Baseline restored: {{ localisation.baseline_restored }}. Original discrepancy preserved: {{ localisation.original_discrepancy_preserved }}.</p><pre>{{ localisation.injection }}</pre><p>{{ localisation.mapping_limitation }}</p></section>{% endif %}
{% if inventory %}<section><h2>Separate RVV mechanism inventory</h2><p>This static inventory comes from the freestanding probe, not the native model binary. Static presence alone does not establish execution or causality.</p><p>Binary SHA-256: <code>{{ inventory.binary_sha256 }}</code></p><table><tr><th>Instruction</th><th>Site</th><th>Mapping</th></tr>{% for site in inventory.sites %}<tr><td>{{ site.mnemonic }}</td><td><code>{{ site.site_id }}</code></td><td>{{ site.source_candidates }}</td></tr>{% endfor %}</table></section>{% endif %}
<section><h2>Archived evidence</h2><p>Raw outputs, requests and execution metadata are covered by the bundle index. The index provides integrity, not external authentication.</p><ul>{% for name,href in links %}<li><a href="{{ href }}">{{ name }}</a></li>{% endfor %}</ul><details><summary>Per-execution result files</summary><ul>{% for name,href in joblinks %}<li><a href="{{ href }}">{{ name }}</a></li>{% endfor %}</ul></details></section>
</html>"""


def render_report(root, output, localisation=None, inventory=None):
    import os

    root = Path(root).resolve()
    output = Path(output).resolve()
    derived = rederive(root)
    if localisation is not None:
        from ..replay.localise import verify_localisation

        localisation = verify_localisation(localisation)
        if localisation["source_bundle_sha256"] != derived["bundle_sha256"]:
            from ..errors import VFGError

            raise VFGError("localisation belongs to another qualification")
    if inventory is not None:
        inventory = load_document(inventory)
    inputs = load_document(root / "inputs.json")
    run = load_document(root / "run.json")
    verdict = derived["verdict"]
    output.mkdir(parents=True, exist_ok=True)
    links = [
        (name, os.path.relpath(root / name, output))
        for name in ["bundle.json", "verdict.json", "inputs.json", "run.json", "margins.json"]
    ]
    jobs = [
        (
            f"{j['case_id']} / {j['role']} / {j['mode']} / {j['repetition']}",
            os.path.relpath(root / j["path"] / "output/result.json", output),
        )
        for j in run["jobs"]
    ]
    template = Environment(autoescape=select_autoescape(default=True)).from_string(TEMPLATE)
    html = template.render(
        localisation=localisation,
        inventory=inventory,
        inputs=inputs,
        run=run,
        verdict=verdict,
        sha=derived["bundle_sha256"],
        rendered=now(),
        margins=derived["margins"],
        divergences=verdict["rules"][0]["first_divergences"] if verdict["rules"] else [],
        stable=sum(x["stable"] for x in verdict["evidence"]["stability"]),
        links=links,
        joblinks=jobs,
        color={"PASS": "#16723a", "FAIL": "#b42318", "INCONCLUSIVE": "#8a5c00", "ERROR": "#b42318"}[
            verdict["verdict"]
        ],
    )
    path = output / "index.html"
    path.write_text(html)
    return path
