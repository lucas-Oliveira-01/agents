"""Deduplication, merging, precedence, and conflict detection for audit-normalize."""

import json
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    CANONICAL_CONFLICT_TYPES,
    PRECEDENCE_RANKING,
    SourceRole,
    make_provenance,
    make_semantic_field,
    make_source_backed_string,
    map_category,
    map_confidence,
    map_finding_status,
    map_finding_type,
    map_severity,
)
from .parser import parse_location


def are_locations_compatible(
    loc1: Optional[Dict[str, Any]],
    loc2: Optional[Dict[str, Any]],
    strict_line_match: bool = False,
) -> bool:
    """Evaluate location compatibility per NCS-0030 (COMPARE_LOCATION_RANGES)."""
    if not loc1 or not loc2:
        return False
    val1 = loc1.get("value")
    val2 = loc2.get("value")
    if not val1 or not val2:
        return False

    file1 = val1.get("file")
    file2 = val2.get("file")
    if not file1 or not file2 or file1 != file2:
        return False

    lines1 = _get_line_bounds(val1)
    lines2 = _get_line_bounds(val2)

    if lines1 is None and lines2 is None:
        return True

    if lines1 is None or lines2 is None:
        if strict_line_match:
            return False
        return True

    s1, e1 = lines1
    s2, e2 = lines2

    return max(s1, s2) <= min(e1, e2)


def _get_line_bounds(val: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    if not isinstance(val, dict):
        return None
    if "line" in val and val["line"] is not None:
        return val["line"], val["line"]
    if "line_start" in val and "line_end" in val and val["line_start"] is not None and val["line_end"] is not None:
        return val["line_start"], val["line_end"]
    return None


def _get_field_primitive(field_dict: Any) -> Any:
    if isinstance(field_dict, dict):
        return field_dict.get("value")
    return field_dict


def _get_comparable_key(primitive: Any) -> Any:
    """Return a hashable representation for set/dict comparison."""
    if isinstance(primitive, (dict, list)):
        return json.dumps(primitive, sort_keys=True)
    return primitive


def resolve_target_project(
    raw_projects: List[Dict[str, Any]],
    sources_dict: Dict[str, Any],
    conflict_counter: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], int]:
    """Resolve target project fields across sources using precedence and conflict detection."""
    conflicts: List[Dict[str, Any]] = []

    default_prov = [make_provenance(raw_projects[0]["source_id"], raw_projects[0]["file"])] if raw_projects else [make_provenance("src-001", "UNKNOWN")]

    target_project: Dict[str, Any] = {}
    fields = ["repository", "commit", "branch", "version", "build_version"]

    for fname in fields:
        contributions = []  # (source_id, source_role, file, val)
        for rp in raw_projects:
            val = rp.get(fname)
            if val is not None and str(val).strip():
                contributions.append((rp["source_id"], rp.get("source_role", "UNKNOWN"), rp["file"], str(val).strip()))

        if not contributions:
            target_project[fname] = make_source_backed_string(
                "NOT_PROVIDED_BY_SOURCE",
                value=None,
                provenance=default_prov,
            )
        elif len(contributions) == 1:
            sid, _, f, v = contributions[0]
            target_project[fname] = make_source_backed_string(
                "PRESENT",
                value=v,
                provenance=[make_provenance(sid, f)],
            )
        else:
            distinct_values = {_get_comparable_key(c[3]) for c in contributions}
            all_prov = [make_provenance(c[0], c[2]) for c in contributions]

            if len(distinct_values) == 1:
                target_project[fname] = make_source_backed_string(
                    "PRESENT",
                    value=contributions[0][3],
                    provenance=all_prov,
                )
            else:
                conflict_counter += 1
                cid = f"CONFLICT-{conflict_counter:03d}"

                ranked = []
                for sid, role, f, v in contributions:
                    rank = PRECEDENCE_RANKING.get(role, 99)
                    ranked.append((rank, sid, f, v))

                ranked.sort(key=lambda x: x[0])
                min_rank = ranked[0][0]
                best = [x for x in ranked if x[0] == min_rank]
                best_values = {_get_comparable_key(x[3]) for x in best}

                conflict_values = [
                    {"source_id": sid, "value": v}
                    for _, sid, _, v in ranked
                ]

                if len(best_values) == 1 and len(best) < len(ranked):
                    winner = best[0]
                    target_project[fname] = make_source_backed_string(
                        "PRESENT",
                        value=winner[3],
                        provenance=all_prov,
                    )
                    conflicts.append({
                        "id": cid,
                        "type": "TARGET_PROJECT_CONFLICT",
                        "finding_id": None,
                        "field": fname,
                        "resolution": {
                            "status": "RESOLVED",
                            "policy_applied": "SOURCE_ROLE_PRECEDENCE",
                            "selected_source": winner[1],
                        },
                        "values": conflict_values,
                    })
                else:
                    target_project[fname] = make_source_backed_string(
                        "CONFLICT",
                        value=None,
                        conflict_id=cid,
                        provenance=all_prov,
                    )
                    conflicts.append({
                        "id": cid,
                        "type": "TARGET_PROJECT_CONFLICT",
                        "finding_id": None,
                        "field": fname,
                        "resolution": {
                            "status": "UNRESOLVED",
                            "policy_applied": None,
                            "selected_source": None,
                        },
                        "values": conflict_values,
                    })

    return target_project, conflicts, conflict_counter


def merge_and_resolve_findings(
    raw_findings: List[Dict[str, Any]],
    sources_dict: Dict[str, Dict[str, Any]],
    conflict_counter: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """Deduplicate findings, apply non-destructive merge, detect conflicts, and resolve by precedence."""
    conflicts: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []

    grouped_by_id: Dict[str, List[Dict[str, Any]]] = {}
    without_id: List[Dict[str, Any]] = []

    for rf in raw_findings:
        fid = rf.get("id")
        if fid:
            grouped_by_id.setdefault(fid, []).append(rf)
        else:
            without_id.append(rf)

    clusters: List[Dict[str, Any]] = []

    for fid, group in grouped_by_id.items():
        if len(group) == 1:
            clusters.append({"id": fid, "items": group})
        else:
            first_raw = group[0].get("_raw", {})
            first_raw_cat = first_raw.get("Category")
            first_cat, _ = map_category(first_raw_cat)
            first_raw_type = first_raw.get("Type")
            first_type, _ = map_finding_type(first_raw_type)
            first_loc = parse_location(first_raw.get("Location"))
            first_loc_val = first_loc.get("value") if first_loc.get("state") == "PRESENT" else None

            is_collision = False
            collision_reason = ""
            for other in group[1:]:
                other_raw = other.get("_raw", {})
                other_raw_cat = other_raw.get("Category")
                other_cat, _ = map_category(other_raw_cat)
                other_raw_type = other_raw.get("Type")
                other_type, _ = map_finding_type(other_raw_type)
                other_loc = parse_location(other_raw.get("Location"))
                other_loc_val = other_loc.get("value") if other_loc.get("state") == "PRESENT" else None

                # Category mismatch
                if first_cat and other_cat and first_cat != other_cat:
                    is_collision = True
                    collision_reason = f"incompatible categories: {first_cat} vs {other_cat}"
                    break
                if first_raw_cat and other_raw_cat and str(first_raw_cat).strip().upper() != str(other_raw_cat).strip().upper():
                    is_collision = True
                    collision_reason = f"incompatible categories: {first_raw_cat} vs {other_raw_cat}"
                    break

                # Type mismatch
                if first_type and other_type and first_type != other_type:
                    is_collision = True
                    collision_reason = f"incompatible types: {first_type} vs {other_type}"
                    break
                if first_raw_type and other_raw_type and str(first_raw_type).strip().upper() != str(other_raw_type).strip().upper():
                    is_collision = True
                    collision_reason = f"incompatible types: {first_raw_type} vs {other_raw_type}"
                    break

                # Location mismatch
                if first_loc_val and other_loc_val:
                    f_file = first_loc_val.get("file")
                    o_file = other_loc_val.get("file")
                    if f_file and o_file and f_file != o_file:
                        is_collision = True
                        collision_reason = f"incompatible location files: {f_file} vs {o_file}"
                        break
                    if not are_locations_compatible(first_loc, other_loc, strict_line_match=False):
                        is_collision = True
                        collision_reason = f"incompatible line locations in {f_file}"
                        break

            if is_collision:
                anomalies.append({
                    "id": f"ANOM-{len(anomalies) + 1:03d}",
                    "type": "ID_COLLISION",
                    "severity": "ERROR",
                    "description": f"Finding ID collision detected for {fid} across sources: {collision_reason}",
                    "provenance": [make_provenance(item["source_id"], item["file"]) for item in group],
                })
                for idx, item in enumerate(group):
                    disambiguated_item = dict(item)
                    dis_id = f"{fid}-{idx + 1:03d}"
                    disambiguated_item["id"] = dis_id
                    clusters.append({"id": dis_id, "items": [disambiguated_item]})
            else:
                clusters.append({"id": fid, "items": group})

    no_id_clusters: List[Dict[str, Any]] = []

    def _matches_cluster(un_item: Dict[str, Any], cl: Dict[str, Any]) -> bool:
        c_un = _build_canonical_finding(un_item, sources_dict)
        un_loc = c_un.get("location")
        if not un_loc or un_loc.get("state") != "PRESENT":
            return False

        c_cand = _build_canonical_finding(cl["items"][0], sources_dict)
        cand_loc = c_cand.get("location")
        if not cand_loc or cand_loc.get("state") != "PRESENT":
            return False

        if not are_locations_compatible(un_loc, cand_loc, strict_line_match=True):
            return False

        if c_un["category"] != c_cand["category"]:
            return False

        un_type = c_un["type"].get("value")
        cand_type = c_cand["type"].get("value")
        if un_type and cand_type and un_type != cand_type:
            return False

        return True

    for un_f in without_id:
        all_existing = clusters + no_id_clusters
        matched_clusters = [cl for cl in all_existing if _matches_cluster(un_f, cl)]

        if len(matched_clusters) == 0:
            no_id_clusters.append({"id": None, "items": [un_f]})
        elif len(matched_clusters) == 1:
            matched_clusters[0]["items"].append(un_f)
        else:
            no_id_clusters.append({"id": None, "items": [un_f]})
            anomalies.append({
                "id": f"ANOM-{len(anomalies) + 1:03d}",
                "type": "CONTRADICTORY_STATEMENT",
                "severity": "WARNING",
                "description": f"Finding without ID in '{un_f.get('file', '')}' matched multiple distinct candidates structurally; kept separate.",
                "provenance": [make_provenance(un_f["source_id"], un_f["file"])],
            })

    # Deterministic sorting of no-id clusters before assigning IDs
    no_id_clusters.sort(key=lambda cl: (
        cl["items"][0].get("file", ""),
        cl["items"][0].get("title", ""),
    ))

    used_ids = {cl["id"] for cl in clusters if cl.get("id")}
    gen_counter = 1
    for cl in no_id_clusters:
        while True:
            gen_id = f"FINDING-{gen_counter:03d}"
            if gen_id not in used_ids:
                used_ids.add(gen_id)
                break
            gen_counter += 1
        cl["id"] = gen_id

    merged_findings: List[Dict[str, Any]] = []
    # Discard clusters that contain solely recommendation items (recommendation != finding)
    valid_clusters = [
        cl for cl in (clusters + no_id_clusters)
        if any(not it.get("_in_recommendations", False) for it in cl["items"])
    ]
    for cl in valid_clusters:
        cid = cl["id"]
        group = cl["items"]
        for it in group:
            it["id"] = cid

        if len(group) == 1:
            canonical = _build_canonical_finding(group[0], sources_dict)
            merged_findings.append(canonical)
        else:
            merged_f, new_conflicts, conflict_counter = _merge_finding_group(
                group, sources_dict, conflict_counter
            )
            merged_findings.append(merged_f)
            conflicts.extend(new_conflicts)

        for it in group:
            for an in it.get("_anomalies", []):
                anomalies.append({
                    "id": f"ANOM-{len(anomalies) + 1:03d}",
                    "type": an["type"],
                    "severity": an.get("severity", "WARNING"),
                    "description": an["description"],
                    "provenance": an.get("provenance", [make_provenance(it["source_id"], it["file"])]),
                })

    merged_findings.sort(key=lambda f: f["id"])
    conflicts.sort(key=lambda c: c["id"])

    return merged_findings, conflicts, anomalies, conflict_counter


def _build_canonical_finding(item: Dict[str, Any], sources_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Map raw item dictionary to canonical schema finding."""
    raw = item.get("_raw", {})
    source_id = item["source_id"]
    file_path = item["file"]
    prov = [make_provenance(source_id, file_path)]
    item_anomalies = item.setdefault("_anomalies", [])
    item_id = item.get("id") or "UNSPECIFIED"

    title = raw.get("Title") or (item.get("title") if item.get("title") != item.get("id") else None) or raw.get("Title") or item.get("title") or "Untitled"

    raw_cat = raw.get("Category")
    canon_cat, is_cat_mapped = map_category(raw_cat)
    if canon_cat:
        category = canon_cat
    elif raw_cat and not is_cat_mapped:
        item_anomalies.append({
            "type": "UNMAPPED_TAXONOMY",
            "severity": "WARNING",
            "description": f"Unmapped taxonomy value '{raw_cat}' for category in finding '{item_id}'",
            "provenance": prov,
        })
        category = None
    else:
        if not item.get("_in_recommendations"):
            item_anomalies.append({
                "type": "SOURCE_FORMAT_ANOMALY",
                "severity": "WARNING",
                "description": f"Category not provided by source for finding '{item_id}'",
                "provenance": prov,
            })
        category = None

    raw_subcat = raw.get("Subcategory")
    subcategory = raw_subcat if raw_subcat and raw_subcat not in ("-", "N/A", "null") else None

    raw_type = raw.get("Type")
    canon_type, is_type_mapped = map_finding_type(raw_type)
    if canon_type:
        type_field = make_semantic_field("PRESENT", value=canon_type)
    elif raw_type and not is_type_mapped:
        type_field = make_semantic_field("NOT_DETERMINABLE", value=None, reason=f"Unmapped taxonomy value: '{raw_type}'")
        item_anomalies.append({
            "type": "UNMAPPED_TAXONOMY",
            "severity": "WARNING",
            "description": f"Unmapped taxonomy value '{raw_type}' for type in finding '{item_id}'",
            "provenance": prov,
        })
    else:
        type_field = make_semantic_field("NOT_PROVIDED_BY_SOURCE", value=None)

    raw_status = raw.get("Status")
    canon_status, is_status_mapped = map_finding_status(raw_status)
    if canon_status:
        status_field = make_semantic_field("PRESENT", value=canon_status)
    elif raw_status and not is_status_mapped:
        status_field = make_semantic_field("NOT_DETERMINABLE", value=None, reason=f"Unmapped taxonomy value: '{raw_status}'")
        item_anomalies.append({
            "type": "UNMAPPED_TAXONOMY",
            "severity": "WARNING",
            "description": f"Unmapped taxonomy value '{raw_status}' for status in finding '{item_id}'",
            "provenance": prov,
        })
    else:
        status_field = make_semantic_field("NOT_PROVIDED_BY_SOURCE", value=None)

    raw_sev = raw.get("Severity")
    canon_sev, is_sev_mapped = map_severity(raw_sev)
    if canon_sev:
        sev_field = make_semantic_field("PRESENT", value=canon_sev)
    elif raw_sev and not is_sev_mapped:
        sev_field = make_semantic_field("NOT_DETERMINABLE", value=None, reason=f"Unmapped taxonomy value: '{raw_sev}'")
        item_anomalies.append({
            "type": "UNMAPPED_TAXONOMY",
            "severity": "WARNING",
            "description": f"Unmapped taxonomy value '{raw_sev}' for severity in finding '{item_id}'",
            "provenance": prov,
        })
    else:
        sev_field = make_semantic_field("NOT_PROVIDED_BY_SOURCE", value=None)

    raw_conf = raw.get("Confidence")
    canon_conf, is_conf_mapped = map_confidence(raw_conf)
    if canon_conf:
        conf_field = make_semantic_field("PRESENT", value=canon_conf)
    elif raw_conf and not is_conf_mapped:
        conf_field = make_semantic_field("NOT_DETERMINABLE", value=None, reason=f"Unmapped taxonomy value: '{raw_conf}'")
        item_anomalies.append({
            "type": "UNMAPPED_TAXONOMY",
            "severity": "WARNING",
            "description": f"Unmapped taxonomy value '{raw_conf}' for confidence in finding '{item_id}'",
            "provenance": prov,
        })
    else:
        conf_field = make_semantic_field("NOT_PROVIDED_BY_SOURCE", value=None)

    raw_loc = raw.get("Location")
    loc_field = parse_location(raw_loc)

    def get_text_field(key: str) -> Dict[str, Any]:
        val = raw.get(key)
        if val and str(val).strip():
            return make_semantic_field("PRESENT", value=str(val).strip())
        return make_semantic_field("NOT_PROVIDED_BY_SOURCE", value=None)

    evidence_field = get_text_field("Evidence")
    desc_field = get_text_field("Description")

    # If description absent, use body lines only if not in recommendations section
    if desc_field["state"] == "NOT_PROVIDED_BY_SOURCE" and item.get("_body_lines"):
        if not item.get("_in_recommendations", False):
            body_text = "\n".join(item["_body_lines"]).strip()
            if body_text:
                desc_field = make_semantic_field("PRESENT", value=body_text)

    cause_field = get_text_field("Cause")
    impact_field = get_text_field("Impact")
    exploit_field = get_text_field("Exploitability")
    rec_field = get_text_field("Recommendation")

    # If in recommendations section and rec_field is empty, assign body lines to recommendation
    if rec_field["state"] == "NOT_PROVIDED_BY_SOURCE" and item.get("_in_recommendations", False) and item.get("_body_lines"):
        rec_body = "\n".join(item["_body_lines"]).strip()
        if rec_body:
            rec_field = make_semantic_field("PRESENT", value=rec_body)

    return {
        "id": item["id"],
        "title": title,
        "category": category,
        "subcategory": subcategory,
        "type": type_field,
        "status": status_field,
        "severity": sev_field,
        "confidence": conf_field,
        "location": loc_field,
        "evidence": evidence_field,
        "description": desc_field,
        "cause": cause_field,
        "impact": impact_field,
        "exploitability": exploit_field,
        "recommendation": rec_field,
        "provenance": prov,
    }


def _merge_finding_group(
    group: List[Dict[str, Any]],
    sources_dict: Dict[str, Any],
    conflict_counter: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], int]:
    """Merge a group of finding entries with identical ID."""
    conflicts: List[Dict[str, Any]] = []

    group_with_rank = []
    for it in group:
        role = it.get("source_role", "UNKNOWN")
        rank = PRECEDENCE_RANKING.get(role, 99)
        group_with_rank.append((rank, it))
    group_with_rank.sort(key=lambda x: x[0])
    group = [x[1] for x in group_with_rank]

    canonical_list = [_build_canonical_finding(item, sources_dict) for item in group]

    base = canonical_list[0]

    seen_provs = {(p["source_id"], p["file"]) for p in base["provenance"]}
    for other in canonical_list[1:]:
        for p in other["provenance"]:
            key = (p["source_id"], p["file"])
            if key not in seen_provs:
                seen_provs.add(key)
                base["provenance"].append(p)

    fields_to_check = [
        ("severity", "SEVERITY_CONFLICT"),
        ("status", "STATUS_CONFLICT"),
        ("confidence", "CONFIDENCE_CONFLICT"),
        ("type", "TYPE_CONFLICT"),
        ("location", "LOCATION_CONFLICT"),
        ("description", "FIELD_VALUE_CONFLICT"),
        ("evidence", "FIELD_VALUE_CONFLICT"),
        ("cause", "FIELD_VALUE_CONFLICT"),
        ("impact", "FIELD_VALUE_CONFLICT"),
        ("exploitability", "FIELD_VALUE_CONFLICT"),
        ("recommendation", "FIELD_VALUE_CONFLICT"),
    ]

    for field_name, conflict_type in fields_to_check:
        values_per_source: List[Tuple[str, str, Any]] = []
        for c_find, raw_item in zip(canonical_list, group):
            f_val = c_find[field_name]
            sid = raw_item["source_id"]
            role = raw_item.get("source_role", "UNKNOWN")
            values_per_source.append((sid, role, f_val))

        present_values = [v for v in values_per_source if v[2].get("state") == "PRESENT"]

        if not present_values:
            continue
        elif len(present_values) == 1:
            base[field_name] = present_values[0][2]
        else:
            distinct_keys = set()
            for sid, role, f_dict in present_values:
                prim = _get_field_primitive(f_dict)
                key = _get_comparable_key(prim)
                distinct_keys.add(key)

            if len(distinct_keys) == 1:
                base[field_name] = present_values[0][2]
            else:
                conflict_counter += 1
                cid = f"CONFLICT-{conflict_counter:03d}"

                ranked_sources = []
                for sid, role, f_dict in present_values:
                    rank = PRECEDENCE_RANKING.get(role, 99)
                    ranked_sources.append((rank, sid, f_dict))

                ranked_sources.sort(key=lambda x: x[0])
                min_rank = ranked_sources[0][0]
                best_candidates = [x for x in ranked_sources if x[0] == min_rank]
                best_primitives = {_get_comparable_key(_get_field_primitive(x[2])) for x in best_candidates}

                conflict_values = [
                    {"source_id": sid, "value": _get_field_primitive(f_dict)}
                    for sid, _, f_dict in present_values
                ]

                if len(best_primitives) == 1 and len(best_candidates) < len(ranked_sources):
                    winner_sid = best_candidates[0][1]
                    winner_fdict = best_candidates[0][2]

                    base[field_name] = dict(winner_fdict)
                    base[field_name]["conflict_id"] = None

                    conflicts.append({
                        "id": cid,
                        "type": conflict_type,
                        "finding_id": base["id"],
                        "field": field_name,
                        "resolution": {
                            "status": "RESOLVED",
                            "policy_applied": "SOURCE_ROLE_PRECEDENCE",
                            "selected_source": winner_sid,
                        },
                        "values": conflict_values,
                    })
                else:
                    base[field_name] = {
                        "state": "CONFLICT",
                        "value": None,
                        "conflict_id": cid,
                    }
                    conflicts.append({
                        "id": cid,
                        "type": conflict_type,
                        "finding_id": base["id"],
                        "field": field_name,
                        "resolution": {
                            "status": "UNRESOLVED",
                            "policy_applied": None,
                            "selected_source": None,
                        },
                        "values": conflict_values,
                    })

    return base, conflicts, conflict_counter


def merge_and_resolve_controls(
    raw_controls: List[Dict[str, Any]],
    sources_dict: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Deduplicate controls by ID, merge provenance, and track unmapped taxonomies."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for c in raw_controls:
        cid = c["id"]
        grouped.setdefault(cid, []).append(c)

    merged: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []

    for cid, group in grouped.items():
        first = group[0]
        raw = first.get("_raw", {})
        title = raw.get("Title") or (first.get("title") if first.get("title") != cid else None) or raw.get("Title") or first.get("title") or "Untitled Control"

        all_provs = []
        seen_p = set()
        for item in group:
            p = make_provenance(item["source_id"], item["file"])
            key = (p["source_id"], p["file"])
            if key not in seen_p:
                seen_p.add(key)
                all_provs.append(p)

        raw_cat = raw.get("Category")
        canon_cat, is_cat_mapped = map_category(raw_cat)
        if canon_cat:
            category = canon_cat
        elif raw_cat and not is_cat_mapped:
            anomalies.append({
                "id": f"ANOM-{len(anomalies) + 1:03d}",
                "type": "UNMAPPED_TAXONOMY",
                "severity": "WARNING",
                "description": f"Unmapped taxonomy value '{raw_cat}' for category in control '{cid}'",
                "provenance": all_provs,
            })
            category = None
        else:
            anomalies.append({
                "id": f"ANOM-{len(anomalies) + 1:03d}",
                "type": "SOURCE_FORMAT_ANOMALY",
                "severity": "WARNING",
                "description": f"Category not provided by source for control '{cid}'",
                "provenance": all_provs,
            })
            category = None

        raw_subcat = raw.get("Subcategory")
        subcategory = raw_subcat if raw_subcat and raw_subcat not in ("-", "N/A", "null") else None

        raw_status = raw.get("Status")
        canon_st, is_st_mapped = map_finding_status(raw_status)
        if canon_st:
            status = canon_st
        elif raw_status and not is_st_mapped:
            anomalies.append({
                "id": f"ANOM-{len(anomalies) + 1:03d}",
                "type": "UNMAPPED_TAXONOMY",
                "severity": "WARNING",
                "description": f"Unmapped taxonomy value '{raw_status}' for status in control '{cid}'",
                "provenance": all_provs,
            })
            status = "NOT_DETERMINABLE"
        else:
            anomalies.append({
                "id": f"ANOM-{len(anomalies) + 1:03d}",
                "type": "SOURCE_FORMAT_ANOMALY",
                "severity": "WARNING",
                "description": f"Status not provided by source for control '{cid}'",
                "provenance": all_provs,
            })
            status = "NOT_DETERMINABLE"

        desc = raw.get("Description") or "\n".join(first.get("_body_lines", [])) or title

        merged.append({
            "id": cid,
            "category": category,
            "subcategory": subcategory,
            "title": title,
            "status": status,
            "description": desc,
            "provenance": all_provs,
        })

    merged.sort(key=lambda c: c["id"])
    return merged, anomalies
