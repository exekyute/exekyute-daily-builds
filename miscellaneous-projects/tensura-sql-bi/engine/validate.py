"""Referential-integrity and rule checks for data/tensura.json.

Pure checks with no I/O: validate(data) takes the loaded dataset dict and
returns (errors, warnings). build_db.py runs it before writing anything, and the
test suite runs it directly, so a broken reference is caught before it can reach
the database or the exports.
"""

from collections import Counter

ALLOWED_ROSTERS = {"Ten Great Demon Lords", "Octagram", "Former"}
ALLOWED_ELEMENTS = {"Star", "Frost", "Scorch", "Storm"}
ALLOWED_TIERS = {"Base", "Evolved"}
ALLOWED_SKILL_TYPES = {
    "Unique Skill", "Ultimate Skill", "Extra Skill", "Intrinsic Skill", "Resist Skill"
}


def _dupes(names):
    return [n for n, c in Counter(names).items() if c > 1]


def validate(data):
    """Return (errors, warnings). errors block the build; warnings do not."""
    errors, warnings = [], []

    races = {r["name"] for r in data["races"]}
    nations = {n["name"] for n in data["nations"]}
    skills = {s["name"] for s in data["skills"]}
    factions = {f["name"] for f in data["factions"]}
    arcs = {a["sequence_no"] for a in data["arcs"]}
    char_names = [c["name"] for c in data["characters"]]
    char_set = set(char_names)

    # Names that other rows reference must be unique.
    for label, names in [
        ("race", [r["name"] for r in data["races"]]),
        ("nation", [n["name"] for n in data["nations"]]),
        ("skill", [s["name"] for s in data["skills"]]),
        ("faction", [f["name"] for f in data["factions"]]),
        ("character", char_names),
        ("arc sequence_no", [a["sequence_no"] for a in data["arcs"]]),
    ]:
        for d in _dupes(names):
            errors.append(f"duplicate {label}: {d}")

    # Dimension value domains.
    for r in data["races"]:
        if r["tier"] not in ALLOWED_TIERS:
            errors.append(f"race {r['name']}: tier '{r['tier']}' not in {sorted(ALLOWED_TIERS)}")
    for s in data["skills"]:
        if s["skill_type"] not in ALLOWED_SKILL_TYPES:
            errors.append(f"skill {s['name']}: type '{s['skill_type']}' not allowed")

    # Character references and value checks.
    for c in data["characters"]:
        nm = c["name"]
        if c["race"] not in races:
            errors.append(f"{nm}: unknown race '{c['race']}'")
        if c.get("nation") is not None and c["nation"] not in nations:
            errors.append(f"{nm}: unknown nation '{c['nation']}'")
        if c.get("debut_arc") is not None and c["debut_arc"] not in arcs:
            errors.append(f"{nm}: unknown debut_arc {c['debut_arc']}")
        ep = c.get("ep_estimate")
        if ep is not None and (not isinstance(ep, int) or ep < 0):
            errors.append(f"{nm}: bad ep_estimate {ep!r}")
        for s in c.get("skills", []):
            if s["skill"] not in skills:
                errors.append(f"{nm}: unknown skill '{s['skill']}'")
        for f in c.get("factions", []):
            if f["faction"] not in factions:
                errors.append(f"{nm}: unknown faction '{f['faction']}'")
        for e in c.get("evolutions", []):
            if e.get("arc") is not None and e["arc"] not in arcs:
                errors.append(f"{nm}: evolution arc {e['arc']} unknown")
        dl = c.get("demon_lord")
        if dl and dl.get("roster") not in ALLOWED_ROSTERS:
            errors.append(f"{nm}: demon_lord roster '{dl.get('roster')}' not allowed")
        td = c.get("true_dragon")
        if td:
            if td.get("element") not in ALLOWED_ELEMENTS:
                errors.append(f"{nm}: true_dragon element '{td.get('element')}' not allowed")
            if td.get("birth_order") not in (1, 2, 3, 4):
                errors.append(f"{nm}: true_dragon birth_order {td.get('birth_order')!r} not 1-4")

    # A nation's ruler, when set, has to be one of the modelled characters.
    for n in data["nations"]:
        if n.get("ruler") is not None and n["ruler"] not in char_set:
            errors.append(f"nation {n['name']}: ruler '{n['ruler']}' is not a character")

    # Soft checks: worth knowing about, but not fatal.
    owned = {s["skill"] for c in data["characters"] for s in c.get("skills", [])}
    for s in sorted(skills - owned):
        warnings.append(f"skill with no owner: {s}")
    joined = {f["faction"] for c in data["characters"] for f in c.get("factions", [])}
    for f in sorted(factions - joined):
        warnings.append(f"faction with no members: {f}")

    td_count = sum(1 for c in data["characters"] if c.get("true_dragon"))
    if td_count != 4:
        warnings.append(f"expected 4 True Dragons, found {td_count}")

    return errors, warnings
