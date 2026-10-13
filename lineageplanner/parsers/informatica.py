"""Informatica PowerCenter XML parser: sources/targets, mappings, sessions, workflows."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from lineageplanner.models import (
    CALLS, DATASET, JOB, MAPPING, READS, WRITES, dataset_id, node_id,
)
from lineageplanner.parsers.base import Parsed, Parser


class InformaticaParser(Parser):
    name = "informatica"
    extensions = (".xml",)

    def matches(self, path: Path) -> bool:
        if path.suffix.lower() != ".xml":
            return False
        head = path.read_text(errors="ignore")[:400]
        return "POWERMART" in head or "REPOSITORY" in head

    def parse(self, path: Path, relpath: str, text: str) -> Parsed:
        p = Parsed()
        root = ET.fromstring(text)

        for m in root.iter("MAPPING"):
            name = m.get("NAME")
            map_node = p.node(node_id(MAPPING, name), name, MAPPING, "informatica", relpath)
            for el in m.iter("TRANSFORMATION"):
                ttype = (el.get("TYPE") or "").lower()
                if ttype == "source qualifier":
                    src = el.get("NAME", "").replace("SQ_", "")
                    p.node(dataset_id(src), src, DATASET, "informatica", relpath)
                    p.edge(dataset_id(src), map_node.id, READS, "source qualifier")
            for el in m.iter("SOURCE"):
                s = el.get("NAME")
                p.node(dataset_id(s), s, DATASET, "informatica", relpath)
                p.edge(dataset_id(s), map_node.id, READS, "mapping source")
            for el in m.iter("TARGET"):
                t = el.get("NAME")
                p.node(dataset_id(t), t, DATASET, "informatica", relpath)
                p.edge(map_node.id, dataset_id(t), WRITES, "mapping target")

        for s in root.iter("SESSION"):
            sess = p.node(node_id(JOB, s.get("NAME")), s.get("NAME"), JOB, "informatica", relpath)
            mapping = s.get("MAPPINGNAME")
            if mapping:
                p.edge(sess.id, node_id(MAPPING, mapping), CALLS, "session mapping")

        for wf in root.iter("WORKFLOW"):
            job = p.node(node_id(JOB, wf.get("NAME")), wf.get("NAME"), JOB, "informatica", relpath)
            for t in wf.iter("TASK"):
                task = p.node(node_id(JOB, t.get("NAME")), t.get("NAME"), JOB, "informatica", relpath,
                              {"task_type": t.get("TYPE")})
                p.edge(job.id, task.id, CALLS, f"task {t.get('TYPE')}")
            for link in wf.iter("WORKFLOWLINK"):
                p.edge(node_id(JOB, link.get("FROMTASK")), node_id(JOB, link.get("TOTASK")),
                       "after", "workflow link")
        return p
