"""
Ownership graph builder for Cytoscape.js rendering.

Builds a directed acyclic graph from matter documents representing corporate
ownership structure, then overlays contradiction edges from detection results.
"""

import logging
import re
import uuid

from backend.documents import DocumentType, get_matter

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def build_ownership_graph(matter_id: str) -> dict:
    """
    Build a Cytoscape.js-compatible graph from matter data.

    Returns dict with 'nodes' and 'edges' arrays, each element having
    a 'data' dict compatible with cy.add().
    """
    matter = get_matter(matter_id)
    if not matter:
        raise ValueError(f"Matter {matter_id} not found")

    nodes = {}
    edges = []
    node_names = set()

    # Parse documents to extract entities and relationships
    for doc in matter.documents:
        text = doc.raw_text

        if doc.doc_type == DocumentType.ASIC_EXTRACT:
            _parse_asic_extract(text, nodes, edges, node_names)
        elif doc.doc_type == DocumentType.SHAREHOLDER_REGISTER:
            _parse_shareholder_register(text, nodes, edges, node_names)

    # Add contradiction edges
    for contra in matter.contradictions:
        if isinstance(contra, dict):
            _add_contradiction_edge(contra, nodes, edges)

    # Build final output
    graph_data = {
        "nodes": [{"data": n} for n in nodes.values()],
        "edges": [{"data": e} for e in edges],
    }

    matter.graph_data = graph_data
    return graph_data


def _parse_asic_extract(text: str, nodes: dict, edges: list, node_names: set):
    """Extract entities from ASIC extract text."""
    lines = text.split("\n")

    # Look for company name and ACN
    for line in lines:
        acn_match = re.search(r"ACN[\s:]*(\d{3}\s?\d{3}\s?\d{3})", line)
        company_match = re.search(r"(?:Company Name|Entity Name)[\s:]*(.+?)(?:\s*ACN|\s*$)", line, re.IGNORECASE)

        if not company_match:
            # Try to find Pty Ltd pattern
            pty_match = re.search(r"([A-Z][A-Za-z\s]+(?:Pty|PTY)\s+(?:Ltd|LTD))", line)
            if pty_match:
                name = pty_match.group(1).strip()
                node_id = _slugify(name)
                if node_id not in nodes:
                    acn = acn_match.group(1) if acn_match else ""
                    nodes[node_id] = {
                        "id": node_id,
                        "label": f"{name}\n{acn}".strip(),
                        "type": "Company",
                        "name": name,
                        "acn": acn,
                    }
                    node_names.add(name)
        elif company_match:
            name = company_match.group(1).strip()
            node_id = _slugify(name)
            if node_id not in nodes:
                acn = acn_match.group(1) if acn_match else ""
                nodes[node_id] = {
                    "id": node_id,
                    "label": f"{name}\n{acn}".strip(),
                    "type": "Company",
                    "name": name,
                    "acn": acn,
                }
                node_names.add(name)

    # Look for directors
    in_directors = False
    for line in lines:
        if re.search(r"(?:directors?|officeholders?)", line, re.IGNORECASE):
            in_directors = True
            continue
        if in_directors and re.search(r"(?:share|capital|registered)", line, re.IGNORECASE):
            in_directors = False
            continue

        if in_directors:
            # Match "Name - Director" or "Name, Director" patterns
            dir_match = re.search(
                r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-,]\s*(?:Director|Secretary|Sole Director)",
                line, re.IGNORECASE,
            )
            if dir_match:
                name = dir_match.group(1).strip()
                node_id = _slugify(name)
                date_match = re.search(r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", line)
                appt_date = date_match.group(1) if date_match else ""

                if node_id not in nodes:
                    nodes[node_id] = {
                        "id": node_id,
                        "label": f"{name}\n{appt_date}".strip() if appt_date else name,
                        "type": "Director",
                        "name": name,
                        "appointment_date": appt_date,
                    }
                    node_names.add(name)

    # Look for share classes
    for line in lines:
        class_match = re.search(
            r"(\d[\d,]*)\s+(Ordinary|Class\s+[A-Z][\w\s]*?)\s+(?:Shares?|shares?)",
            line, re.IGNORECASE,
        )
        if class_match:
            quantity = class_match.group(1).replace(",", "")
            class_name = class_match.group(2).strip()
            node_id = _slugify(class_name + "-shares")
            if node_id not in nodes:
                nodes[node_id] = {
                    "id": node_id,
                    "label": f"{class_name} Shares\n({quantity} issued)",
                    "type": "ShareClass",
                    "name": class_name,
                    "quantity": quantity,
                }

    # Look for shareholders
    for line in lines:
        sh_match = re.search(
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+|[A-Z][\w\s]+(?:Pty|PTY)\s+(?:Ltd|LTD))"
            r"\s*[-:,]\s*(\d[\d,]*)\s+(Ordinary|Class\s+[A-Z][\w\s]*?)\s+(?:Shares?|shares?)",
            line, re.IGNORECASE,
        )
        if sh_match:
            name = sh_match.group(1).strip()
            quantity = sh_match.group(2).replace(",", "")
            share_class = sh_match.group(3).strip()
            node_id = _slugify(name)

            if node_id not in nodes:
                nodes[node_id] = {
                    "id": node_id,
                    "label": f"{name}\n{quantity} {share_class}",
                    "type": "Shareholder",
                    "name": name,
                    "shares": quantity,
                    "share_class": share_class,
                }
                node_names.add(name)

    # Look for ultimate holding company
    for line in lines:
        uhc_match = re.search(r"(?:Ultimate Holding Company|UHC)[\s:]*(.+?)(?:\s*ACN|\s*$)", line, re.IGNORECASE)
        if uhc_match:
            name = uhc_match.group(1).strip()
            if name and name.lower() not in ("none", "n/a", "nil"):
                node_id = _slugify(name)
                if node_id not in nodes:
                    nodes[node_id] = {
                        "id": node_id,
                        "label": name,
                        "type": "UltimateHoldingCompany",
                        "name": name,
                    }
                    node_names.add(name)

    # Detect sole signatory authority patterns
    for line in lines:
        if re.search(r"sole\s+(?:signatory|signing)\s+authority", line, re.IGNORECASE):
            sole_match = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", line)
            if sole_match:
                name = sole_match.group(1).strip()
                node_id = _slugify(name)
                if node_id in nodes:
                    nodes[node_id]["sole_signatory"] = True


def _parse_shareholder_register(text: str, nodes: dict, edges: list, node_names: set):
    """Extract shareholder entries from register."""
    lines = text.split("\n")
    for line in lines:
        sh_match = re.search(
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+|[A-Z][\w\s]+(?:Pty|PTY)\s+(?:Ltd|LTD))"
            r"[\s|,]+(\d[\d,]*)\s+(Ordinary|Class\s+[A-Z][\w\s]*?)\s+(?:Shares?|shares?)",
            line, re.IGNORECASE,
        )
        if sh_match:
            name = sh_match.group(1).strip()
            quantity = sh_match.group(2).replace(",", "")
            share_class = sh_match.group(3).strip()
            node_id = _slugify(name)

            if node_id not in nodes:
                nodes[node_id] = {
                    "id": node_id,
                    "label": f"{name}\n{quantity} {share_class}",
                    "type": "Shareholder",
                    "name": name,
                    "shares": quantity,
                    "share_class": share_class,
                }
                node_names.add(name)


def _add_contradiction_edge(contra: dict, nodes: dict, edges: list):
    """Add a red contradiction edge between relevant nodes."""
    edge_id = f"contra-{contra.get('contradiction_id', str(uuid.uuid4())[:8])}"
    edges.append({
        "id": edge_id,
        "source": _slugify(contra.get("source_section", "unknown")),
        "target": _slugify(contra.get("target_section", "unknown")),
        "type": "CONTRADICTION",
        "label": contra.get("typology_label", "Contradiction"),
        "severity": contra.get("severity", "medium"),
        "contradiction_id": contra.get("contradiction_id", ""),
        "cosine_similarity": contra.get("cosine_similarity", 0),
    })


def build_graph_from_entities(matter_id: str, entities_by_doc: dict) -> dict:
    """
    Build a Cytoscape.js graph from Gemini-extracted OwnershipEntities.

    entities_by_doc maps doc_type string to OwnershipEntities objects.
    This is more reliable than regex parsing raw text.
    """
    matter = get_matter(matter_id)
    if not matter:
        raise ValueError(f"Matter {matter_id} not found")

    nodes = []
    edges = []
    node_ids = set()

    # Extract company info (prefer ASIC extract)
    company = None
    for doc_type in ["asic_extract", "constitution", "shareholder_register"]:
        ent = entities_by_doc.get(doc_type)
        if ent and ent.company and ent.company.name:
            company = ent.company
            break

    if company and company.name:
        company_id = _slugify(company.name)
        nodes.append({"data": {
            "id": company_id,
            "label": f"{company.name}\nACN {company.acn}" if company.acn else company.name,
            "type": "Company",
            "name": company.name,
            "acn": company.acn,
        }})
        node_ids.add(company_id)
    else:
        company_id = "company"
        company_name = matter.entity_name or "Unknown Company"
        nodes.append({"data": {
            "id": company_id,
            "label": company_name,
            "type": "Company",
            "name": company_name,
            "acn": matter.acn,
        }})
        node_ids.add(company_id)

    # Directors (from ASIC extract)
    asic_ent = entities_by_doc.get("asic_extract")
    if asic_ent:
        for i, d in enumerate(asic_ent.directors):
            did = _slugify(d.name)
            if did not in node_ids:
                label = f"{d.name}\nAppt: {d.appointment_date}" if d.appointment_date else d.name
                nodes.append({"data": {
                    "id": did,
                    "label": label,
                    "type": "Director",
                    "name": d.name,
                    "appointment_date": d.appointment_date,
                    "sole_signatory": d.sole_signatory,
                }})
                node_ids.add(did)

            edge_label = d.role
            if d.sole_signatory:
                edge_label += " (Sole Signatory)"
            edges.append({"data": {
                "id": f"e-dir-{i}",
                "source": did,
                "target": company_id,
                "type": "CONTROLS",
                "label": edge_label,
            }})

    # Share classes (prefer constitution definitions, fall back to ASIC)
    const_ent = entities_by_doc.get("constitution")
    share_classes = []
    if const_ent and const_ent.share_classes:
        share_classes = const_ent.share_classes
    elif asic_ent and asic_ent.share_classes:
        share_classes = asic_ent.share_classes

    # Track which classes are constitutionally authorised
    const_class_names = set()
    if const_ent:
        const_class_names = {sc.name for sc in const_ent.share_classes}

    # Also add any ASIC-only share classes (potential undisclosed)
    asic_class_names = set()
    if asic_ent:
        for sc in asic_ent.share_classes:
            asic_class_names.add(sc.name)
            if sc.name not in const_class_names:
                # Undisclosed share class
                share_classes.append(sc)

    for i, sc in enumerate(share_classes):
        scid = _slugify(sc.name + "-shares")
        if scid not in node_ids:
            undisclosed = sc.name in asic_class_names and sc.name not in const_class_names
            vote_text = "voting" if sc.voting else "non-voting"
            label = f"{sc.name} Shares\n{sc.quantity} issued\n{vote_text}" if sc.quantity else f"{sc.name} Shares"
            if undisclosed:
                label += "\n(Not in Constitution)"
            nodes.append({"data": {
                "id": scid,
                "label": label,
                "type": "ShareClass",
                "name": sc.name,
                "quantity": str(sc.quantity),
                "undisclosed": undisclosed,
            }})
            node_ids.add(scid)
            edges.append({"data": {
                "id": f"e-sc-{i}",
                "source": scid,
                "target": company_id,
                "type": "ISSUED_UNDER",
                "label": sc.name + (" (Undisclosed)" if undisclosed else ""),
            }})

    # Shareholders (prefer register, fall back to ASIC)
    reg_ent = entities_by_doc.get("shareholder_register")
    shareholders = []
    if reg_ent and reg_ent.shareholders:
        shareholders = reg_ent.shareholders
    elif asic_ent and asic_ent.shareholders:
        shareholders = asic_ent.shareholders

    for i, sh in enumerate(shareholders):
        shid = _slugify(sh.name) + "-sh"
        if shid not in node_ids:
            label = f"{sh.name}\n{sh.quantity} {sh.share_class}"
            nodes.append({"data": {
                "id": shid,
                "label": label,
                "type": "Shareholder",
                "name": sh.name,
                "shares": str(sh.quantity),
                "share_class": sh.share_class,
            }})
            node_ids.add(shid)

        # Calculate ownership percentage
        total = 0
        for sc in share_classes:
            if sc.name == sh.share_class and sc.quantity > 0:
                total = sc.quantity
                break
        pct = f"{round(sh.quantity / total * 100)}%" if total > 0 else ""
        edges.append({"data": {
            "id": f"e-sh-{i}",
            "source": shid,
            "target": company_id,
            "type": "OWNS",
            "label": f"{pct} {sh.share_class}" if pct else sh.share_class,
        }})

    # Ultimate holding company
    uhc_name = ""
    if asic_ent and asic_ent.ultimate_holding_company:
        uhc_name = asic_ent.ultimate_holding_company
    if uhc_name and uhc_name.lower() not in ("none", "n/a", "nil", "none recorded", ""):
        uhcid = _slugify(uhc_name)
        if uhcid not in node_ids:
            nodes.append({"data": {
                "id": uhcid,
                "label": uhc_name,
                "type": "UltimateHoldingCompany",
                "name": uhc_name,
            }})
            node_ids.add(uhcid)
            edges.append({"data": {
                "id": "e-uhc",
                "source": uhcid,
                "target": company_id,
                "type": "CONTROLS",
                "label": "Ultimate Holding Company",
            }})

    # Add contradiction edges, mapping to relevant node pairs
    all_node_ids = [n["data"]["id"] for n in nodes]
    for i, contra in enumerate(matter.contradictions):
        c = contra if isinstance(contra, dict) else contra.model_dump()
        typology_id = c.get("typology_id", "")
        source_doc = c.get("source_doc_type", "")
        target_doc = c.get("target_doc_type", "")

        # Map contradiction to relevant graph nodes based on typology
        src, tgt = company_id, company_id
        if "nominee" in typology_id or "trust" in typology_id:
            # Find a corporate shareholder node (likely nominee)
            nominee_nodes = [n["data"]["id"] for n in nodes
                            if n["data"].get("type") == "Shareholder"
                            and "pty" in n["data"].get("name", "").lower()]
            if nominee_nodes:
                src = nominee_nodes[0]
                tgt = company_id
        elif "share_class" in typology_id or "undisclosed" in typology_id:
            # Find undisclosed share class node
            undisclosed_nodes = [n["data"]["id"] for n in nodes
                                if n["data"].get("undisclosed")]
            if undisclosed_nodes:
                src = undisclosed_nodes[0]
                # Link to the first non-undisclosed share class
                normal_sc = [n["data"]["id"] for n in nodes
                             if n["data"].get("type") == "ShareClass"
                             and not n["data"].get("undisclosed")]
                tgt = normal_sc[0] if normal_sc else company_id
        elif "layered" in typology_id or "concealment" in typology_id:
            # Find a sole signatory director
            sole_dirs = [n["data"]["id"] for n in nodes
                         if n["data"].get("sole_signatory")]
            if sole_dirs:
                src = sole_dirs[0]
                tgt = company_id

        edges.append({"data": {
            "id": f"e-contra-{i}",
            "source": src,
            "target": tgt,
            "type": "CONTRADICTION",
            "label": c.get("typology_label", "Contradiction"),
            "severity": c.get("severity", "medium"),
            "contradiction_id": c.get("contradiction_id", ""),
            "cosine_similarity": c.get("cosine_similarity", 0),
        }})

    graph_data = {"nodes": nodes, "edges": edges}
    matter.graph_data = graph_data
    return graph_data


def build_fixture_graph(matter_id: str, fixture_id: str) -> dict:
    """
    Build a hardcoded graph for fixture data where entities are known.
    This avoids regex parsing of free text for demo reliability.
    """
    matter = get_matter(matter_id)
    if not matter:
        raise ValueError(f"Matter {matter_id} not found")

    nodes = []
    edges = []

    # Company node
    nodes.append({"data": {
        "id": "fixture-holdings",
        "label": "Fixture Holdings Pty Ltd\nACN 000 000 001",
        "type": "Company",
        "name": "Fixture Holdings Pty Ltd",
        "acn": "000 000 001",
    }})

    # Directors
    nodes.append({"data": {
        "id": "james-mitchell",
        "label": "James Mitchell\nAppt: 01/07/2020",
        "type": "Director",
        "name": "James Mitchell",
        "appointment_date": "01/07/2020",
        "sole_signatory": fixture_id == "B",
    }})
    nodes.append({"data": {
        "id": "sarah-blackwood",
        "label": "Sarah Blackwood\nAppt: 01/07/2020",
        "type": "Director",
        "name": "Sarah Blackwood",
        "appointment_date": "01/07/2020",
    }})

    # Director -> Company edges
    edges.append({"data": {
        "id": "e-james-dir",
        "source": "james-mitchell",
        "target": "fixture-holdings",
        "type": "CONTROLS",
        "label": "Director" + (" (Sole Signatory)" if fixture_id == "B" else ""),
    }})
    edges.append({"data": {
        "id": "e-sarah-dir",
        "source": "sarah-blackwood",
        "target": "fixture-holdings",
        "type": "CONTROLS",
        "label": "Director & Secretary",
    }})

    # Shareholders
    nodes.append({"data": {
        "id": "james-mitchell-sh",
        "label": "James Mitchell\n400 Ordinary",
        "type": "Shareholder",
        "name": "James Mitchell",
        "shares": "400",
        "share_class": "Ordinary",
    }})
    nodes.append({"data": {
        "id": "pacific-trust",
        "label": "Pacific Trust Services\nPty Ltd\n600 Ordinary",
        "type": "Shareholder",
        "name": "Pacific Trust Services Pty Ltd",
        "shares": "600",
        "share_class": "Ordinary",
    }})
    nodes.append({"data": {
        "id": "sarah-blackwood-sh",
        "label": "Sarah Blackwood\n500 Class B Pref",
        "type": "Shareholder",
        "name": "Sarah Blackwood",
        "shares": "500",
        "share_class": "Class B Preference",
    }})

    # Ownership edges
    edges.append({"data": {
        "id": "e-james-owns",
        "source": "james-mitchell-sh",
        "target": "fixture-holdings",
        "type": "OWNS",
        "label": "40% Ordinary",
    }})
    edges.append({"data": {
        "id": "e-pacific-owns",
        "source": "pacific-trust",
        "target": "fixture-holdings",
        "type": "OWNS",
        "label": "60% Ordinary",
    }})
    edges.append({"data": {
        "id": "e-sarah-owns",
        "source": "sarah-blackwood-sh",
        "target": "fixture-holdings",
        "type": "OWNS",
        "label": "100% Class B Pref",
    }})

    # Share class nodes
    nodes.append({"data": {
        "id": "ordinary-shares",
        "label": "Ordinary Shares\n1,000 issued\n1 vote per share",
        "type": "ShareClass",
        "name": "Ordinary",
        "quantity": "1000",
    }})
    nodes.append({"data": {
        "id": "class-b-pref",
        "label": "Class B Preference\n500 issued\nNon-voting",
        "type": "ShareClass",
        "name": "Class B Preference",
        "quantity": "500",
    }})

    # Share class edges
    edges.append({"data": {
        "id": "e-ord-class",
        "source": "ordinary-shares",
        "target": "fixture-holdings",
        "type": "ISSUED_UNDER",
        "label": "Ordinary",
    }})
    edges.append({"data": {
        "id": "e-pref-class",
        "source": "class-b-pref",
        "target": "fixture-holdings",
        "type": "ISSUED_UNDER",
        "label": "Class B Preference",
    }})

    # Fixture B: add extra undisclosed share class node
    if fixture_id == "B":
        nodes.append({"data": {
            "id": "class-c-conv",
            "label": "Class C Convertible\nPreference\n(Not in Constitution)",
            "type": "ShareClass",
            "name": "Class C Convertible Preference",
            "quantity": "0",
            "undisclosed": True,
        }})
        edges.append({"data": {
            "id": "e-class-c",
            "source": "class-c-conv",
            "target": "fixture-holdings",
            "type": "ISSUED_UNDER",
            "label": "Class C (Undisclosed)",
        }})

    # Add contradiction edges for fixture B
    if fixture_id == "B" and matter.contradictions:
        for i, contra in enumerate(matter.contradictions):
            if isinstance(contra, dict):
                c = contra
            else:
                c = contra.model_dump() if hasattr(contra, "model_dump") else contra

                # Map contradictions to specific graph node pairs
            typology_id = c.get("typology_id", "")

            if "nominee" in typology_id:
                src, tgt = "pacific-trust", "fixture-holdings"
            elif "share_class" in typology_id or "undisclosed" in typology_id:
                src, tgt = "class-c-conv", "ordinary-shares"
            elif "layered" in typology_id or "concealment" in typology_id:
                src, tgt = "james-mitchell", "fixture-holdings"
            else:
                src, tgt = "fixture-holdings", "pacific-trust"

            edges.append({"data": {
                "id": f"e-contra-{i}",
                "source": src,
                "target": tgt,
                "type": "CONTRADICTION",
                "label": c.get("typology_label", "Contradiction"),
                "severity": c.get("severity", "medium"),
                "contradiction_id": c.get("contradiction_id", ""),
                "cosine_similarity": c.get("cosine_similarity", 0),
            }})

    graph_data = {"nodes": nodes, "edges": edges}
    matter.graph_data = graph_data
    return graph_data
