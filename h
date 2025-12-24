warning: in the working copy of 'webapp/app.py', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'webapp/static/style.css', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'webapp/templates/index.html', LF will be replaced by CRLF the next time Git touches it
[1mdiff --git a/webapp/app.py b/webapp/app.py[m
[1mindex bdcfd3a..a3b7722 100644[m
[1m--- a/webapp/app.py[m
[1m+++ b/webapp/app.py[m
[36m@@ -411,7 +411,14 @@[m [mdef _attach_explain(results: List[Any], model: Optional[str]) -> List[Any]:[m
             if isinstance(r, dict) and "explain" not in r:[m
                 code = _extract_error_code_from_result(r)[m
                 if code and code in catalog:[m
[31m-                    r["explain"] = catalog[code][m
[32m+[m[32m                    explain_data = catalog[code][m
[32m+[m[32m                    if "metadata" not in r or not isinstance(r.get("metadata"), dict):[m
[32m+[m[32m                        r["metadata"] = {}[m
[32m+[m[32m                    if isinstance(explain_data, dict):[m
[32m+[m[32m                        r["metadata"].update(explain_data)[m
[32m+[m[32m                    else:[m
[32m+[m[32m                        r["metadata"].update({"explain": explain_data})[m
[32m+[m[32m                    r["explain"] = explain_data[m
         except Exception:[m
             continue[m
     return results[m
[1mdiff --git a/webapp/static/style.css b/webapp/static/style.css[m
[1mindex c3217af..da996e6 100644[m
[1m--- a/webapp/static/style.css[m
[1m+++ b/webapp/static/style.css[m
[36m@@ -356,6 +356,67 @@[m [mselect:focus {[m
   color: #e5e7eb;[m
 }[m
 [m
[32m+[m[32m.bmk-link-btn {[m
[32m+[m[32m  background: transparent;[m
[32m+[m[32m  border: none;[m
[32m+[m[32m  padding: 0;[m
[32m+[m[32m  margin: 0;[m
[32m+[m[32m  color: #cbd5f5;[m
[32m+[m[32m  text-decoration: underline;[m
[32m+[m[32m  cursor: pointer;[m
[32m+[m[32m  font: inherit;[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m.bmk-link-btn:hover {[m
[32m+[m[32m  color: #e5e7eb;[m
[32m+[m[32m  text-decoration: underline;[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m.bmk-link-btn:focus-visible {[m
[32m+[m[32m  outline: 2px solid rgba(203, 213, 245, 0.6);[m
[32m+[m[32m  outline-offset: 2px;[m
[32m+[m[32m  border-radius: 2px;[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m.traffic {[m
[32m+[m[32m  display: inline-block;[m
[32m+[m[32m  font-size: 12px;[m
[32m+[m[32m  font-weight: 700;[m
[32m+[m[32m  letter-spacing: 0.04em;[m
[32m+[m[32m  text-transform: uppercase;[m
[32m+[m[32m  padding: 4px 8px;[m
[32m+[m[32m  border-radius: 999px;[m
[32m+[m[32m  border: 1px solid transparent;[m
[32m+[m[32m  line-height: 1.2;[m
[32m+[m[32m  margin-right: 6px;[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m.traffic-info {[m
[32m+[m[32m  color: #93c5fd;[m
[32m+[m[32m  background: rgba(59, 130, 246, 0.15);[m
[32m+[m[32m  border-color: rgba(59, 130, 246, 0.35);[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m.traffic-warn {[m
[32m+[m[32m  color: #fbbf24;[m
[32m+[m[32m  background: rgba(245, 158, 11, 0.15);[m
[32m+[m[32m  border-color: rgba(245, 158, 11, 0.35);[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m.traffic-critical {[m
[32m+[m[32m  color: #f87171;[m
[32m+[m[32m  background: rgba(239, 68, 68, 0.15);[m
[32m+[m[32m  border-color: rgba(239, 68, 68, 0.35);[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m.traffic-advice {[m
[32m+[m[32m  margin-top: 6px;[m
[32m+[m[32m  font-size: 13px;[m
[32m+[m[32m  opacity: 0.9;[m
[32m+[m[32m  line-height: 1.35;[m
[32m+[m[32m  color: #d1d5db;[m
[32m+[m[32m}[m
[32m+[m
 /* BMK-Details (Toggle) */[m
 [m
 .bmk-details {[m
[1mdiff --git a/webapp/templates/index.html b/webapp/templates/index.html[m
[1mindex e26d8b1..795f6af 100644[m
[1m--- a/webapp/templates/index.html[m
[1m+++ b/webapp/templates/index.html[m
[36m@@ -364,7 +364,14 @@[m
           const model = r.model || meta.model || 'Unbekanntes Modell';[m
           const rawSource = r.source_type || meta.source_type || r.source || meta.source || '';[m
           const sourceLabel = mapSourceLabel(rawSource);[m
[31m-          header.textContent = model + ' · ' + sourceLabel + ' · explain=' + (r.explain ? 'yes' : 'no');[m
[32m+[m[32m          header.textContent = model + ' · ' + sourceLabel;[m
[32m+[m
[32m+[m[32m          const sensorText = (meta.sensor_name || meta.geber_name || meta.title || '').toString();[m
[32m+[m[32m          const bmkMatch = sensorText.match(/BMK\s*([A-Z]\d{1,4}(?:[.\-]\w{1,6})?)/i);[m
[32m+[m[32m          let bmkCode = bmkMatch ? bmkMatch[1].toUpperCase().trim() : '';[m
[32m+[m[32m          if (!bmkCode && meta.bmk) {[m
[32m+[m[32m            bmkCode = String(meta.bmk).toUpperCase().trim();[m
[32m+[m[32m          }[m
 [m
           if (r.score != null) {[m
             card.title = 'Score: ' + Number(r.score).toFixed(3);[m
[36m@@ -373,17 +380,7 @@[m
           const metaBox = document.createElement('div');[m
           metaBox.className = 'result-meta';[m
 [m
[31m-          const bmkDebug = createMetaRow('BMK-DEBUG', JSON.stringify({[m
[31m-            bmk: meta.bmk,[m
[31m-            bmk_code: meta.bmk_code,[m
[31m-            bmk_match: meta.bmk_match,[m
[31m-            linked_bmk: meta.linked_bmk,[m
[31m-            bmk_candidates: meta.bmk_candidates[m
[31m-          }));[m
[31m-          if (bmkDebug) metaBox.appendChild(bmkDebug);[m
[31m-[m
           const errorCode = (meta.code || meta.error_code || '').toString().trim();[m
[31m-          const bmkCode = (meta.bmk || '').toString().trim();[m
 [m
           const rawDesc = meta.description || meta.beschreibung || '';[m
           const usefulDesc = extractUsefulDescription(rawDesc);[m
[36m@@ -400,8 +397,39 @@[m
             if (codeRow) metaBox.appendChild(codeRow);[m
           }[m
           if (bmkCode && isLikelyBmkCode(bmkCode)) {[m
[31m-            const bmkRow = createMetaRow('BMK', bmkCode);[m
[31m-            if (bmkRow) metaBox.appendChild(bmkRow);[m
[32m+[m[32m            const row = document.createElement('div');[m
[32m+[m[32m            row.className = 'meta-row';[m
[32m+[m
[32m+[m[32m            const l = document.createElement('span');[m
[32m+[m[32m            l.className = 'meta-label';[m
[32m+[m[32m            l.textContent = 'BMK:';[m
[32m+[m
[32m+[m[32m            const v = document.createElement('span');[m
[32m+[m[32m            v.className = 'meta-value';[m
[32m+[m
[32m+[m[32m            const btn = document.createElement('button');[m
[32m+[m[32m            btn.type = 'button';[m
[32m+[m[32m            btn.className = 'bmk-link-btn';[m
[32m+[m[32m            btn.textContent = bmkCode;[m
[32m+[m[32m            btn.addEventListener('click', () => {[m
[32m+[m[32m              const q = document.getElementById('bmk_query');[m
[32m+[m[32m              const m = document.getElementById('bmk_model');[m
[32m+[m[32m              if (q) q.value = bmkCode;[m
[32m+[m[32m              if (m) m.value = model;[m
[32m+[m[32m              const f = document.getElementById('bmk-form');[m
[32m+[m[32m              if (f) {[m
[32m+[m[32m                if (typeof f.requestSubmit === 'function') {[m
[32m+[m[32m                  f.requestSubmit();[m
[32m+[m[32m                } else {[m
[32m+[m[32m                  f.dispatchEvent(new Event('submit', { cancelable: true }));[m
[32m+[m[32m                }[m
[32m+[m[32m              }[m
[32m+[m[32m            });[m
[32m+[m
[32m+[m[32m            v.appendChild(btn);[m
[32m+[m[32m            row.appendChild(l);[m
[32m+[m[32m            row.appendChild(v);[m
[32m+[m[32m            metaBox.appendChild(row);[m
           }[m
 [m
           // ✅ hier kommt jetzt der Klartext rein (z.B. "Tastatureinheit links")[m
[36m@@ -441,12 +469,35 @@[m
 [m
           if (r.explain) {[m
             const explain = r.explain || {};[m
[32m+[m[32m            const sevRaw = (explain.severity || '').toString().toLowerCase().trim();[m
[32m+[m[32m            const operable = (explain.operable === false) ? false : true;[m
[32m+[m[32m            let sev = 'info';[m
[32m+[m[32m            if (!operable) sev = 'critical';[m
[32m+[m[32m            else if (sevRaw === 'critical' || sevRaw === 'kritisch') sev = 'critical';[m
[32m+[m[32m            else if (sevRaw === 'warn' || sevRaw === 'warning' || sevRaw === 'warnung') sev = 'warn';[m
[32m+[m[32m            else sev = 'info';[m
[32m+[m
[32m+[m[32m            let trafficLabel = 'INFO';[m
[32m+[m[32m            let trafficAdvice = 'Hinweis. Beobachten, bei Wiederholung prüfen.';[m
[32m+[m[32m            if (sev === 'critical') {[m
[32m+[m[32m              trafficLabel = 'KRITISCH';[m
[32m+[m[32m              trafficAdvice = 'Nicht weiter betreiben. Ursache sofort prüfen.';[m
[32m+[m[32m            } else if (sev === 'warn') {[m
[32m+[m[32m              trafficLabel = 'WARNUNG';[m
[32m+[m[32m              trafficAdvice = 'Weiterbetrieb möglich, aber zeitnah prüfen / Service planen.';[m
[32m+[m[32m            }[m
[32m+[m
             const explainBox = document.createElement('div');[m
             explainBox.className = 'explain-box';[m
 [m
             const headerRow = document.createElement('div');[m
             headerRow.className = 'explain-header';[m
 [m
[32m+[m[32m            const traffic = document.createElement('span');[m
[32m+[m[32m            traffic.className = 'traffic ' + (sev === 'critical' ? 'traffic-critical' : (sev === 'warn' ? 'traffic-warn' : 'traffic-info'));[m
[32m+[m[32m            traffic.textContent = trafficLabel;[m
[32m+[m[32m            headerRow.appendChild(traffic);[m
[32m+[m
             const titleEl = document.createElement('div');[m
             titleEl.className = 'explain-title';[m
             titleEl.textContent = cleanDisplayText(explain.title || '');[m
[36m@@ -462,6 +513,11 @@[m
 [m
             explainBox.appendChild(headerRow);[m
 [m
[32m+[m[32m            const trafficAdviceEl = document.createElement('div');[m
[32m+[m[32m            trafficAdviceEl.className = 'traffic-advice';[m
[32m+[m[32m            trafficAdviceEl.textContent = trafficAdvice;[m
[32m+[m[32m            explainBox.appendChild(trafficAdviceEl);[m
[32m+[m
             function addExplainSection(label, value) {[m
               const cleaned = cleanDisplayText(value || '');[m
               if (!cleaned) return;[m
[36m@@ -730,6 +786,10 @@[m
               }[m
               setStatus(bmkStatus, 'Treffer: ' + data.results.length, 'ok');[m
               renderResults(bmkResults, data.results);[m
[32m+[m[32m              const target = bmkResults.querySelector('.result-card') || bmkResults;[m
[32m+[m[32m              if (target && target.scrollIntoView) {[m
[32m+[m[32m                target.scrollIntoView({ behavior: 'smooth', block: 'start' });[m
[32m+[m[32m              }[m
             })[m
             .catch(err => {[m
               console.error(err);[m
