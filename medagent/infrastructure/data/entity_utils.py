"""
Entity ID utility functions for Phase 14 data architecture.

Provides mapping between free text (NER output, user queries) and
standardized entity IDs defined in core_entities.json.
"""
import json
import unicodedata
from pathlib import Path
from typing import Optional


def load_entity_mapping(path: str = "data/entity_standard_id_mapping.json") -> dict:
    """
    Load the flattened entity mapping from JSON file.

    Returns a dict with structure:
    {
        "name_to_id": {"高血压": "DISEASE_001", "HTN": "DISEASE_001", ...},
        "id_to_name": {"DISEASE_001": "高血压", ...},
        "id_to_category": {"DISEASE_001": "cardiovascular", ...}
    }
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_text(text: str) -> str:
    """Normalize text for matching: NFC unicode + strip + lowercase for English."""
    text = unicodedata.normalize("NFC", text).strip()
    return text


def map_text_to_ent_ids(text: str, mapping: dict) -> list[str]:
    """
    Map free text to standard_id list (optimized v4: v2 + negation rules).

    Best performing version: v2 base + manual negation rules for common false positives.

    Parameters
    ----------
    text : str
        Free text to search for entities
    mapping : dict
        Loaded entity mapping from load_entity_mapping()

    Returns
    -------
    list[str]
        Matched standard_ids
    """
    text_normalized = normalize_text(text)
    name_to_id = mapping.get("name_to_id", {})

    # 否定规则：如果文本包含这些模式，跳过对应实体
    negation_rules = {
        "肝功能": ["转氨酶", "谷丙转氨酶", "谷草转氨酶", "ALT", "AST"],  # 避免"转氨酶"误匹配"肝功能"
        "肾功能": ["肌酐", "尿素氮", "BUN", "Cr"],  # 避免"肌酐"误匹配"肾功能"
        "多食": ["食物", "食欲", "饮食"],  # 避免"食"误匹配"多食"
        "多饮": ["饮食", "饮水"],  # 避免"饮"误匹配"多饮"
    }

    # 按长度降序排序
    sorted_names = sorted(name_to_id.items(), key=lambda x: len(x[0]), reverse=True)

    matched_ids = set()
    matched_spans = []

    for name, std_id in sorted_names:
        # 跳过单字词
        if len(name) == 1:
            continue

        # 检查否定规则
        skip = False
        for neg_entity, neg_keywords in negation_rules.items():
            if name == neg_entity:
                for keyword in neg_keywords:
                    if keyword in text_normalized:
                        skip = True
                        break
            if skip:
                break

        if skip:
            continue

        # 查找所有匹配位置
        start = 0
        while True:
            pos = text_normalized.find(name, start)
            if pos == -1:
                break

            end = pos + len(name)

            # 检查重叠
            overlap = any(s < end and pos < e for s, e in matched_spans)
            if not overlap:
                matched_ids.add(std_id)
                matched_spans.append((pos, end))

            start = pos + 1

    return sorted(matched_ids)


def ent_id_to_standard_name(ent_id: str, mapping: dict) -> Optional[str]:
    """
    Convert a standard_id to its canonical Chinese name.

    Parameters
    ----------
    ent_id : str
        Standard entity ID, e.g. "DISEASE_001"
    mapping : dict
        Loaded entity mapping from load_entity_mapping()

    Returns
    -------
    str or None
        Canonical name (e.g. "高血压"), or None if not found
    """
    return mapping.get("id_to_name", {}).get(ent_id)


def build_mapping_from_core_entities(core_entities_path: str = "data/core_entities.json") -> dict:
    """
    Build the flattened entity mapping from core_entities.json.

    This is used by scripts/define_core_entities.py to generate
    data/entity_standard_id_mapping.json.
    """
    with open(core_entities_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    name_to_id = {}
    id_to_name = {}
    id_to_category = {}

    entity_types = ["diseases", "drugs", "symptoms", "tests", "allergies"]

    for entity_type in entity_types:
        entities = data.get(entity_type, [])
        for entity in entities:
            std_id = entity["standard_id"]
            name = normalize_text(entity["name"])
            category = entity.get("category", "")

            id_to_name[std_id] = entity["name"]
            id_to_category[std_id] = category
            name_to_id[name] = std_id

            for synonym in entity.get("synonyms", []):
                syn_normalized = normalize_text(synonym)
                if syn_normalized not in name_to_id:
                    name_to_id[syn_normalized] = std_id

    return {
        "name_to_id": name_to_id,
        "id_to_name": id_to_name,
        "id_to_category": id_to_category,
    }


def save_mapping(mapping: dict, output_path: str = "data/entity_standard_id_mapping.json"):
    """Save the flattened mapping to JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
