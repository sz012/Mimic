from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.demo_items import demo_items
from app.sources import load_items, open_store, raw_dir
from engine.cluster import Workspace
from engine.cluster.perspectives import (
    DEFAULT_PERSPECTIVE,
    PERSPECTIVES,
    features_used,
    membership_table,
    run_all,
)
from engine.explain import edge_card
from engine.explain.report import to_csv, to_dataset_csv, to_dataset_json, to_html, to_json
from engine.ingest import ingest_upload
from engine.schema import Item
from engine.similarity import compare
from engine.similarity.compare import formula
from engine.sources import mode as adlib_mode

logger = logging.getLogger(__name__)
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
FACE_FIELDS = {
    "label",
    "name",
    "person",
    "match_id",
    "score",
    "similarity",
    "confidence",
    "bbox",
    "faces",
    "matches",
}


class RateLimiter:
    def __init__(self):
        self.lock = threading.Lock()
        self.hits: dict[tuple[str, str], deque[float]] = {}

    def allow(self, client: str, action: str, maximum: int, window: int) -> bool:
        now = time.monotonic()
        key = (client, action)
        with self.lock:
            if len(self.hits) > 1000:
                self.hits.pop(next(iter(self.hits)))
            recent = self.hits.setdefault(key, deque())
            while recent and now - recent[0] > window:
                recent.popleft()
            if len(recent) >= maximum:
                return False
            recent.append(now)
            return True


def public_face_value(value):
    if isinstance(value, str):
        return value[:120]
    if isinstance(value, list):
        if all(isinstance(part, str) for part in value):
            return [part[:120] for part in value[:50]]
        if len(value) == 4 and all(isinstance(part, (int, float)) for part in value):
            return value
        return [
            {key: public_face_value(part) for key, part in entry.items() if key in FACE_FIELDS}
            for entry in value[:50]
            if isinstance(entry, dict)
        ]
    if isinstance(value, dict):
        return {key: public_face_value(part) for key, part in value.items() if key in FACE_FIELDS}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return None


def feature_rows(item) -> list[dict]:
    rows = []
    for f in sorted(item.features.values(), key=lambda f: (f.group, f.name)):
        row = asdict(f)
        if f.name == "person.faces":
            row["value"] = public_face_value(f.value)
        if f.name == "person.face_vectors":
            row["value"] = {"count": len(f.value) if isinstance(f.value, list) else 0}
        row["truncated"] = isinstance(f.value, list) and len(f.value) > 50
        if row["truncated"]:
            row["value"] = f.value[:50]
        rows.append(row)
    return rows


def public_evidence(evidence):
    row = asdict(evidence)
    if evidence.feature in {"person.faces", "person.face_vectors"}:
        row["left"] = public_face_value(evidence.left)
        row["right"] = public_face_value(evidence.right)
    return row


class SettingsBody(BaseModel):
    threshold: float | None = Field(default=None, ge=0, le=1)
    method: str | None = None
    case_links: bool | None = None


class CompareBody(BaseModel):
    a: str
    b: str


class AddBody(BaseModel):
    upload_id: str


class AdlibBody(BaseModel):
    terms: str = Field(min_length=2, max_length=120)
    countries: list[str] = Field(default_factory=lambda: ["PL"], max_length=5)
    max_pages: int = Field(default=1, ge=1, le=3)


def create_app(workspace: Workspace | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        current()
        yield

    app = FastAPI(title="mimic", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.lock = threading.Lock()
    app.state.uploads = {}
    app.state.workspace = workspace
    app.state.is_demo = workspace is not None
    app.state.raw_dir = Path(workspace.raw_dir if workspace else raw_dir())
    app.state.cache_dir = Path(os.environ.get("MIMIC_CACHE_DIR", "data/cache"))
    app.state.upload_dir = app.state.cache_dir / "uploads"
    app.state.rate_limiter = RateLimiter()

    def limit(request: Request, action: str, maximum: int, window: int = 3600) -> None:
        client = request.client.host if request.client else "unknown"
        if not app.state.rate_limiter.allow(client, action, maximum, window):
            raise HTTPException(429, "Limit żądań został przekroczony. Spróbuj później.")

    def current() -> Workspace:
        with app.state.lock:
            if app.state.workspace is None:
                items = load_items()
                app.state.is_demo = not items
                app.state.workspace = (
                    Workspace(demo_items(), app.state.raw_dir)
                    if not items
                    else Workspace.load(
                        items, app.state.raw_dir, app.state.cache_dir, store=open_store()
                    )
                )
            return app.state.workspace

    def state() -> dict:
        ws = current()
        return {
            "is_demo": app.state.is_demo,
            "stats": ws.stats(),
            "threshold": ws.threshold,
            "method": ws.method,
            "case_links": ws.case_links,
            "formula": formula(ws.weights),
            "faces_enabled": any(
                item.features.get("person.face_vectors")
                and item.features["person.face_vectors"].available
                for item in ws.items
            ),
            "adlib_enabled": adlib_mode() is not None,
            "adlib_mode": adlib_mode(),
            "perspectives": [
                {"key": p.key, "label": p.label, "question": p.question}
                for p in PERSPECTIVES.values()
            ],
            "default_perspective": DEFAULT_PERSPECTIVE,
        }

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request, exc: StarletteHTTPException):
        message = (
            "Nie znaleziono zasobu."
            if exc.status_code == 404 and exc.detail == "Not Found"
            else str(exc.detail)
        )
        return JSONResponse({"error": message}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _exc: RequestValidationError):
        return JSONResponse({"error": "Sprawdź poprawność przesłanych danych."}, status_code=422)

    @app.exception_handler(Exception)
    async def server_error(_request, exc: Exception):
        logger.exception("Błąd API", exc_info=exc)
        return JSONResponse({"error": "Nie udało się wykonać operacji."}, status_code=500)

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/state")
    def get_state():
        return state()

    @app.post("/api/settings")
    def settings(body: SettingsBody, request: Request):
        limit(request, "settings", 60, 60)
        if body.method is not None and body.method not in {"components", "average"}:
            raise HTTPException(422, "Nieznana metoda grupowania.")
        ws = current()
        with app.state.lock:
            ws.recluster(body.threshold, body.method, body.case_links)
            return state_unlocked(ws)

    def state_unlocked(ws: Workspace) -> dict:
        return {
            "is_demo": app.state.is_demo,
            "stats": ws.stats(),
            "threshold": ws.threshold,
            "method": ws.method,
            "case_links": ws.case_links,
            "formula": formula(ws.weights),
            "faces_enabled": any(
                item.features.get("person.face_vectors")
                and item.features["person.face_vectors"].available
                for item in ws.items
            ),
            "adlib_enabled": adlib_mode() is not None,
            "adlib_mode": adlib_mode(),
            "perspectives": [
                {"key": p.key, "label": p.label, "question": p.question}
                for p in PERSPECTIVES.values()
            ],
            "default_perspective": DEFAULT_PERSPECTIVE,
        }

    @app.get("/api/items")
    def items():
        ws = current()
        with app.state.lock:
            return [
                {
                    "id": item.id,
                    "case_id": item.case_id,
                    "kinds": item.kinds,
                    "campaign": ws.label.get(item.id),
                    "singleton": ws.campaign(ws.label[item.id]).is_singleton,
                    "available_features": sum(f.available for f in item.features.values()),
                    "missing_features": sum(not f.available for f in item.features.values()),
                }
                for item in ws.items
            ]

    @app.get("/api/items/{item_id:path}")
    def item_detail(item_id: str):
        ws = current()
        with app.state.lock:
            item = ws.by_id.get(item_id)
            if item is None:
                raise HTTPException(404, "Nie znaleziono materiału.")
            features = feature_rows(item)
            return {
                "id": item.id,
                "case_id": item.case_id,
                "kinds": item.kinds,
                "campaign": ws.label.get(item.id),
                "features": features,
            }

    @app.get("/api/campaigns")
    def campaigns():
        ws = current()
        with app.state.lock:
            return ws.campaign_cards()

    @app.get("/api/campaigns/{campaign_id:path}")
    def campaign(campaign_id: str):
        ws = current()
        with app.state.lock:
            card = ws.card(campaign_id)
            if card is None:
                raise HTTPException(404, "Nie znaleziono kampanii.")
            return card

    @app.get("/api/graph")
    def graph(
        min_edge: float = Query(default=0.3, ge=0, le=1),
        perspective: str = Query(default=DEFAULT_PERSPECTIVE),
    ):
        if perspective not in PERSPECTIVES:
            raise HTTPException(422, "Nieznana perspektywa.")
        ws = current()
        with app.state.lock:
            return ws.graph(min_edge, perspective)

    @app.post("/api/compare")
    def compare_items(body: CompareBody):
        ws = current()
        with app.state.lock:
            a, b = ws.by_id.get(body.a), ws.by_id.get(body.b)
            if a is None or b is None or a.id == b.id:
                raise HTTPException(404, "Wybierz dwa różne materiały ze zbioru.")
            edge = compare(a, b, ws.context, ws.weights)
            if edge is None:
                return {"score": 0, "linked": False, "card": None, "evidence": []}
            card = edge_card(edge, ws.threshold, ws.weights)
            return {
                "score": edge.score,
                "linked": card["linked"],
                "card": card,
                "evidence": [public_evidence(e) for e in edge.evidence],
            }

    @app.get("/api/criteria")
    def criteria(request: Request, case_links: bool = False):
        limit(request, "criteria", 60, 60)
        ws = current()
        with app.state.lock:
            results = run_all(ws.items, ws.threshold, case_links, ws.weights, ws.method)
            return {
                "criteria": [
                    {
                        "key": key,
                        "label": res.perspective.label,
                        "question": res.perspective.question,
                        "campaigns": len(res.real),
                        "grouped_items": sum(len(c.items) for c in res.real),
                        "singletons": len(res.singletons),
                        "features": [
                            {"name": name, "weight": weight, "label": label}
                            for name, weight, label in features_used(key, ws.weights)
                        ],
                        "groups": [[i.id for i in c.items] for c in res.real],
                    }
                    for key, res in results.items()
                ],
                "membership": membership_table(results, ws.items),
                "threshold": ws.threshold,
            }

    def analysis_payload(result, existing: bool) -> dict:
        return {
            "item": {
                "id": result.item.id,
                "case_id": result.item.case_id,
                "kinds": result.item.kinds,
                "media": result.item.paths.get("screenshot", [])[:5],
            },
            "assignment": {
                "item_id": result.assignment.item_id,
                "campaign_id": result.assignment.campaign_id,
                "score": result.assignment.score,
                "evidence": [public_evidence(e) for e in result.assignment.evidence],
            },
            "card": result.card,
            "similar": [{k: v for k, v in row.items() if k != "edge"} for row in result.similar],
            "missing": result.missing,
            "available": result.available,
            "formula": result.formula,
            "best_edge_card": result.best_edge_card,
            "is_new_pattern": result.is_new_pattern,
            "existing": existing,
            "features": feature_rows(result.item),
        }

    @app.post("/api/analyze")
    async def analyze(
        request: Request,
        files: Annotated[list[UploadFile] | None, File()] = None,
        url: Annotated[str | None, Form()] = None,
        existing_id: Annotated[str | None, Form()] = None,
    ):
        limit(request, "analyze", 30)
        files = files or []
        if existing_id:
            ws = current()
            with app.state.lock:
                known = ws.by_id.get(existing_id)
                if known is None:
                    raise HTTPException(404, "Nie znaleziono materiału.")
                result = ws.analyze(known)
                return analysis_payload(result, existing=True)
        if not files and not (url or "").strip():
            raise HTTPException(422, "Dodaj plik lub adres URL.")
        if url:
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise HTTPException(422, "Podaj poprawny adres HTTP lub HTTPS.")
        uploaded = []
        total = 0
        for file in files:
            data = await file.read(MAX_UPLOAD_BYTES - total + 1)
            total += len(data)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "Pliki przekraczają limit 50 MB.")
            uploaded.append((file.filename or "plik", data))
        ws = current()
        with app.state.lock:
            item = ingest_upload(uploaded, url, app.state.upload_dir)
            result = ws.analyze(item, app.state.upload_dir)
            app.state.uploads[item.id] = result.item
            return analysis_payload(result, existing=False)

    @app.post("/api/items")
    def add_item(body: AddBody, request: Request):
        limit(request, "add", 30)
        ws = current()
        with app.state.lock:
            item: Item | None = app.state.uploads.get(body.upload_id)
            if item is None:
                raise HTTPException(404, "Nie znaleziono przeanalizowanego materiału.")
            assignment = ws.add(item, app.state.upload_dir)
            del app.state.uploads[body.upload_id]
            return {"assignment": asdict(assignment), "state": state_unlocked(ws)}

    @app.post("/api/adlib/search")
    def search_ads(body: AdlibBody, request: Request):
        limit(request, "adlib", 30)
        if adlib_mode() is None:
            return {"results": [], "notice": "Biblioteka reklam wymaga tokenu serwera."}
        ws = current()
        with app.state.lock:
            results, notice = ws.search_ads(
                body.terms, body.countries, app.state.cache_dir / "adlib", body.max_pages
            )
            return {
                "results": [
                    {"item": {"id": item.id}, "card": analysis.card} for item, analysis in results
                ],
                "notice": notice,
            }

    @app.get("/api/media")
    def media(path: str):
        for root in (app.state.raw_dir, app.state.upload_dir):
            base = root.resolve()
            candidate = (base / path).resolve()
            if (
                candidate.is_relative_to(base)
                and candidate.is_file()
                and candidate.suffix.lower() in IMAGE_TYPES
            ):
                return FileResponse(
                    candidate,
                    media_type=IMAGE_TYPES[candidate.suffix.lower()],
                    headers={"X-Content-Type-Options": "nosniff"},
                )
        raise HTTPException(404, "Nie znaleziono obrazu.")

    @app.get("/api/export/{format}")
    def export(format: str):
        ws = current()
        with app.state.lock:
            cards = ws.campaign_cards()
            meta = state_unlocked(ws)
            if format == "json":
                content, mime = to_json(cards, meta), "application/json"
            elif format == "csv":
                content, mime = to_csv(cards), "text/csv"
            elif format == "html":
                content, mime = to_html(cards, meta), "text/html"
            elif format == "dataset-json":
                content, mime = to_dataset_json(ws.items, ws.label), "application/json"
            elif format == "dataset-csv":
                content, mime = to_dataset_csv(ws.items, ws.label), "text/csv"
            else:
                raise HTTPException(404, "Nieznany format raportu.")
            return Response(
                content,
                media_type=f"{mime}; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="{"mimic-zbior-cech" if format.startswith("dataset") else "mimic-raport"}.{format.split("-")[-1]}"'
                },
            )

    film = Path(__file__).resolve().parents[1] / "brand" / "film" / "mimic-film.mp4"

    @app.get("/film.mp4")
    def film_file():
        if not film.is_file():
            raise HTTPException(404, "Brak filmu.")
        return FileResponse(film, media_type="video/mp4", headers={"Cache-Control": "no-cache"})

    dist = Path(__file__).resolve().parents[1] / "web" / "dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}")
        def web(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(404, "Nie znaleziono strony.")
            if full_path in {"favicon.svg", "logo.svg", "logo-dark.svg", "logo-mark.svg"}:
                return FileResponse(dist / full_path)
            if full_path and "." in Path(full_path).name:
                raise HTTPException(404, "Nie znaleziono pliku.")
            return FileResponse(dist / "index.html")

    return app


app = create_app()
