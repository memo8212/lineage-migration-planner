"""Elasticsearch parser: index mappings, ingest pipelines, saved searches."""
from __future__ import annotations

import json
from pathlib import Path

from lineageplanner.models import INDEX, PIPELINE, READS, dataset_id, node_id
from lineageplanner.parsers.base import Parsed, Parser


class ElasticsearchParser(Parser):
    name = "elasticsearch"
    extensions = (".json",)

    def matches(self, path: Path) -> bool:
        if path.suffix.lower() != ".json":
            return False
        try:
            doc = json.loads(path.read_text(errors="ignore"))
        except (json.JSONDecodeError, ValueError):
            return False
        if not isinstance(doc, dict):
            return False
        return any(k in doc for k in ("index_patterns", "mappings", "processors", "searches"))

    def parse(self, path: Path, relpath: str, text: str) -> Parsed:
        p = Parsed()
        doc = json.loads(text)

        if "index_patterns" in doc or "mappings" in doc:
            patterns = doc.get("index_patterns") or [path.stem]
            for pat in patterns:
                name = pat.replace("*", "all")
                p.node(dataset_id(name), name, INDEX, "elasticsearch", relpath,
                       {"kind": "index"})

        if "processors" in doc:
            pipe = p.node(node_id(PIPELINE, path.stem), path.stem, PIPELINE, "elasticsearch", relpath,
                          {"processors": len(doc["processors"])})
            for proc in doc["processors"]:
                for op, body in proc.items():
                    if isinstance(body, dict) and "field" in body:
                        p.node(dataset_id(body["field"]), body["field"], "field", "elasticsearch", relpath)
                        p.edge(pipe.id, dataset_id(body["field"]), "transforms", op)

        for s in doc.get("searches", []):
            idx = s.get("index", "").replace("*", "all")
            p.node(dataset_id(idx), idx, INDEX, "elasticsearch", relpath)
            p.node(node_id("search", s.get("name")), s.get("name"), "search", "elasticsearch", relpath)
            p.edge(dataset_id(idx), node_id("search", s.get("name")), READS, "saved search")
        return p
