# Datei: scripts/netlist_extractor.py
"""
Netlist-Extraktion aus Schaltplan-Grafik (Hough + Morphologie).
Optional mit Template-Matching fuer Standardsymbole.
Optional mit Auto-Crop und Auto-Page-Filter fuer Schaltplan-Seiten.

Beispiel:
  python -m scripts.netlist_extractor --input input/LTM1110-5.1/spl/spl_001.pdf --output output/netlist.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pypdfium2 as pdfium  # pip install pypdfium2
from PIL import Image

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    cv2 = None
    np = None


@dataclass
class LineSeg:
    x1: int
    y1: int
    x2: int
    y2: int


def _require_cv() -> None:
    if cv2 is None or np is None:
        raise RuntimeError(
            "Fehlende Abhaengigkeiten: bitte 'opencv-python' und 'numpy' installieren."
        )


def render_page(pdf_path: Path, page_index: int, dpi: int = 200) -> Image.Image:
    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf.get_page(page_index)
    scale = dpi / 72
    bitmap = page.render(scale=scale)
    pil_image: Image.Image = bitmap.to_pil()
    page.close()
    pdf.close()
    return pil_image


def preprocess_image(pil_image: Image.Image) -> "np.ndarray":
    _require_cv()
    img = np.array(pil_image)
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(gray, 50, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, kernel, iterations=1)
    return edges


def auto_crop_image(pil_image: Image.Image) -> Tuple[Image.Image, Optional[Tuple[int, int, int, int]]]:
    _require_cv()
    img = np.array(pil_image)
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return pil_image, None
    h, w = gray.shape[:2]
    best = None
    for cnt in sorted(contours, key=cv2.contourArea, reverse=True):
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            best = cnt
            break
    if best is None:
        best = max(contours, key=cv2.contourArea)
    x, y, bw, bh = cv2.boundingRect(best)
    area = bw * bh
    if area < 0.2 * w * h or area > 0.98 * w * h:
        return pil_image, None
    x1 = max(0, x + 2)
    y1 = max(0, y + 2)
    x2 = min(w, x + bw - 2)
    y2 = min(h, y + bh - 2)
    if x2 <= x1 or y2 <= y1:
        return pil_image, None
    cropped = pil_image.crop((x1, y1, x2, y2))
    return cropped, (x1, y1, x2, y2)


def detect_lines(edges: "np.ndarray") -> List[LineSeg]:
    _require_cv()
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=80,
        minLineLength=40,
        maxLineGap=5,
    )
    segs: List[LineSeg] = []
    if lines is None:
        return segs
    for x1, y1, x2, y2 in lines[:, 0]:
        segs.append(LineSeg(int(x1), int(y1), int(x2), int(y2)))
    return segs


def _line_intersection(a: LineSeg, b: LineSeg) -> Optional[Tuple[float, float]]:
    x1, y1, x2, y2 = a.x1, a.y1, a.x2, a.y2
    x3, y3, x4, y4 = b.x1, b.y1, b.x2, b.y2
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if denom == 0:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
    if 0 <= t <= 1 and 0 <= u <= 1:
        ix = x1 + t * (x2 - x1)
        iy = y1 + t * (y2 - y1)
        return ix, iy
    return None


def cluster_points(points: List[Tuple[float, float]], radius: float = 6.0) -> List[Tuple[float, float]]:
    clusters: List[Tuple[float, float]] = []
    for px, py in points:
        found = False
        for i, (cx, cy) in enumerate(clusters):
            dx = px - cx
            dy = py - cy
            if (dx * dx + dy * dy) <= radius * radius:
                clusters[i] = ((cx + px) / 2.0, (cy + py) / 2.0)
                found = True
                break
        if not found:
            clusters.append((px, py))
    return clusters


def nearest_node_index(nodes: List[Tuple[float, float]], point: Tuple[float, float]) -> int:
    best_idx = -1
    best_dist = float("inf")
    px, py = point
    for i, (nx, ny) in enumerate(nodes):
        dx = px - nx
        dy = py - ny
        dist = dx * dx + dy * dy
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    return best_idx


def build_graph(lines: List[LineSeg], include_intersections: bool = True) -> Dict[str, Any]:
    endpoints: List[Tuple[float, float]] = []
    for ln in lines:
        endpoints.append((ln.x1, ln.y1))
        endpoints.append((ln.x2, ln.y2))

    intersections: List[Tuple[float, float]] = []
    if include_intersections and len(lines) <= 1000:
        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                inter = _line_intersection(lines[i], lines[j])
                if inter is not None:
                    intersections.append(inter)

    nodes = cluster_points(endpoints + intersections, radius=6.0)
    edges: List[Dict[str, Any]] = []
    for ln in lines:
        n1 = nearest_node_index(nodes, (ln.x1, ln.y1))
        n2 = nearest_node_index(nodes, (ln.x2, ln.y2))
        if n1 == -1 or n2 == -1 or n1 == n2:
            continue
        edges.append(
            {
                "from": n1,
                "to": n2,
                "length": float(((ln.x1 - ln.x2) ** 2 + (ln.y1 - ln.y2) ** 2) ** 0.5),
            }
        )

    return {"nodes": nodes, "edges": edges}


def page_classify(edges: "np.ndarray", lines: List[LineSeg]) -> Tuple[str, Dict[str, float]]:
    _require_cv()
    h, w = edges.shape[:2]
    edge_pixels = float((edges > 0).sum())
    edge_density = edge_pixels / max(1.0, float(h * w))
    if not lines:
        return "other", {"edge_density": edge_density, "line_count": 0.0, "hv_ratio": 0.0}

    hv = 0
    long_lines = 0
    for ln in lines:
        dx = abs(ln.x2 - ln.x1)
        dy = abs(ln.y2 - ln.y1)
        if dx < 5 or dy < 5:
            hv += 1
        if (dx * dx + dy * dy) ** 0.5 > min(h, w) * 0.15:
            long_lines += 1

    hv_ratio = hv / max(1, len(lines))
    long_ratio = long_lines / max(1, len(lines))

    row_density = (edges > 0).sum(axis=1) / max(1.0, float(w))
    dense_rows = float((row_density > 0.15).sum()) / max(1.0, float(h))

    short_lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=50,
        minLineLength=10,
        maxLineGap=2,
    )
    short_horiz = 0
    short_total = 0
    if short_lines is not None:
        short_total = int(short_lines.shape[0])
        for x1, y1, x2, y2 in short_lines[:, 0]:
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            if dy <= 2 and dx <= 30:
                short_horiz += 1
    short_horiz_ratio = short_horiz / max(1, short_total)

    looks_like_toc = dense_rows >= 0.12 and short_horiz_ratio >= 0.35 and long_ratio < 0.25

    is_schematic = (
        len(lines) >= 250
        and hv_ratio >= 0.6
        and (edge_density >= 0.01 or long_ratio >= 0.15)
        and not looks_like_toc
    )

    looks_like_table = (
        len(lines) >= 150
        and hv_ratio >= 0.8
        and dense_rows >= 0.2
        and edge_density >= 0.03
    )

    page_type = "schematic" if is_schematic else ("list_table" if looks_like_table else "other")
    return page_type, {
        "edge_density": edge_density,
        "line_count": float(len(lines)),
        "hv_ratio": hv_ratio,
        "long_ratio": long_ratio,
        "dense_rows": dense_rows,
        "short_horiz_ratio": short_horiz_ratio,
        "looks_like_toc": 1.0 if looks_like_toc else 0.0,
        "looks_like_table": 1.0 if looks_like_table else 0.0,
    }


def load_templates(templates_dir: Path) -> List[Tuple[str, "np.ndarray"]]:
    _require_cv()
    templates: List[Tuple[str, "np.ndarray"]] = []
    for path in sorted(templates_dir.glob("*.png")):
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        templates.append((path.stem, img))
    return templates


def detect_symbols(
    gray: "np.ndarray",
    templates: List[Tuple[str, "np.ndarray"]],
    threshold: float = 0.7,
) -> List[Dict[str, Any]]:
    _require_cv()
    detections: List[Dict[str, Any]] = []
    for name, tpl in templates:
        res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
        yloc, xloc = np.where(res >= threshold)
        seen: List[Tuple[int, int]] = []
        h, w = tpl.shape[:2]
        for (x, y) in zip(xloc, yloc):
            if any((abs(x - sx) + abs(y - sy)) < 10 for sx, sy in seen):
                continue
            seen.append((x, y))
            detections.append(
                {
                    "symbol": name,
                    "x": int(x),
                    "y": int(y),
                    "w": int(w),
                    "h": int(h),
                    "score": float(res[y, x]),
                }
            )
    return detections


def process_pdf(
    pdf_path: Path,
    output_path: Path,
    dpi: int,
    debug_dir: Optional[Path],
    templates_dir: Optional[Path],
    page_start: int,
    page_end: Optional[int],
    auto_pages: bool,
    auto_crop: bool,
) -> None:
    _require_cv()
    pdf = pdfium.PdfDocument(str(pdf_path))
    page_count = len(pdf)
    pdf.close()

    templates: List[Tuple[str, "np.ndarray"]] = []
    if templates_dir and templates_dir.exists():
        templates = load_templates(templates_dir)

    pages_out: List[Dict[str, Any]] = []
    start = max(0, page_start)
    end = page_count if page_end is None else min(page_count, page_end)
    for page_index in range(start, end):
        pil_image = render_page(pdf_path, page_index, dpi=dpi)
        crop_box: Optional[Tuple[int, int, int, int]] = None
        if auto_crop:
            pil_image, crop_box = auto_crop_image(pil_image)
        edges = preprocess_image(pil_image)
        lines = detect_lines(edges)
        page_type = "schematic"
        page_score = {}
        if auto_pages:
            page_type, page_score = page_classify(edges, lines)
        graph = build_graph(lines, include_intersections=True) if page_type == "schematic" else {"nodes": [], "edges": []}

        page_out: Dict[str, Any] = {
            "page": page_index,
            "line_count": len(lines),
            "graph": graph,
            "auto_skipped": page_type != "schematic",
            "page_type": page_type,
            "page_score": page_score,
            "crop_box": crop_box,
        }

        if templates:
            gray = edges
            symbols = detect_symbols(gray, templates)
            page_out["symbols"] = symbols

        if debug_dir:
            debug_dir.mkdir(parents=True, exist_ok=True)
            dbg = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            for ln in lines:
                cv2.line(dbg, (ln.x1, ln.y1), (ln.x2, ln.y2), (0, 255, 0), 1)
            for (nx, ny) in graph["nodes"]:
                cv2.circle(dbg, (int(nx), int(ny)), 2, (0, 0, 255), -1)
            out_path = debug_dir / f"page_{page_index:03d}.png"
            cv2.imwrite(str(out_path), dbg)

        pages_out.append(page_out)

    output = {
        "type": "NETLIST_GRAPH",
        "source_file": pdf_path.name,
        "page_count": page_count,
        "page_start": start,
        "page_end": end,
        "pages": pages_out,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Netlist-Extraktion aus SPL-PDFs.")
    ap.add_argument("--input", required=True, help="Pfad zur PDF-Datei")
    ap.add_argument("--output", required=True, help="Pfad zur Output-JSON")
    ap.add_argument("--dpi", type=int, default=200, help="Render-DPI (Standard: 200)")
    ap.add_argument("--page-start", type=int, default=0, help="Startseite (0-basiert)")
    ap.add_argument("--page-end", type=int, help="Ende (exklusiv, 0-basiert)")
    ap.add_argument("--auto-pages", action="store_true", help="Nur Schaltplan-Seiten verarbeiten")
    ap.add_argument("--auto-crop", action="store_true", help="Seiten automatisch auf Rahmen croppen")
    ap.add_argument("--debug-dir", help="Debug-Overlays als PNG speichern")
    ap.add_argument("--templates-dir", help="Symbol-Templates (PNG) fuer Matching")
    args = ap.parse_args(argv)

    pdf_path = Path(args.input)
    output_path = Path(args.output)
    debug_dir = Path(args.debug_dir) if args.debug_dir else None
    templates_dir = Path(args.templates_dir) if args.templates_dir else None

    process_pdf(
        pdf_path,
        output_path,
        args.dpi,
        debug_dir,
        templates_dir,
        args.page_start,
        args.page_end,
        args.auto_pages,
        args.auto_crop,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
