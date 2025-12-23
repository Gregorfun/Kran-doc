Kran-Doc Explain Builder (MVP)

Was du bekommst:
- build_explain_catalog.py
- config/explain_rules.json
- config/explain_templates.json

Ziel:
Automatisch 'Explain-Boxen' erzeugen, ohne für jeden Fehlercode ein Prompt zu bauen.

Installation:
1) Kopiere build_explain_catalog.py ins Projekt-Root.
2) Kopiere die beiden JSONs nach config/.

Run:
python build_explain_catalog.py --models-dir "output/models" --write-aggregated

Output:
- output/models/<MODEL>/explain_catalog.json
- output/explain_catalog_all.json  (optional)

Integration (nächster Schritt):
Im Flask app.py beim Suchtreffer-Rendern:
- explain_catalog.json laden (pro Modell)
- wenn Treffer-Code im Catalog: result["explain"] = catalog[code]
