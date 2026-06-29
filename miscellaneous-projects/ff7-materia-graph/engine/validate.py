"""Validation for the materia dataset.

The indexer runs these checks before it builds the graph, so a typo in the data
turns into a clear message instead of a broken graph. Every function takes the
parsed materia.json dict and returns a list of error strings, empty when the
data is clean.
"""

from ff7_graph import slug


def validate(data):
    """Run every check and return a combined, de-duplicated list of errors."""
    errors = []
    if not isinstance(data, dict):
        return ["The dataset must be a JSON object with materia, categories, and elements."]

    for key in ("categories", "elements", "materia"):
        if key not in data:
            errors.append("Missing required top-level key: '%s'." % key)
    if errors:
        return errors

    category_ids = set()
    for cat in data["categories"]:
        if "id" not in cat or "name" not in cat:
            errors.append("Every category needs an 'id' and a 'name'.")
            continue
        category_ids.add(cat["id"])

    elements = set(slug(e) for e in data["elements"])

    seen_ids = set()
    materia_ids = set()
    for i, m in enumerate(data["materia"]):
        where = "materia entry #%d" % (i + 1)

        mid = m.get("id")
        name = m.get("name")
        if not mid:
            errors.append("%s is missing an 'id'." % where)
        else:
            where = "materia '%s'" % mid
            if slug(mid) != mid:
                errors.append("%s id should be lowercase and hyphenated (got '%s')." % (where, mid))
            if mid in seen_ids:
                errors.append("Duplicate materia id '%s'." % mid)
            seen_ids.add(mid)
            materia_ids.add(mid)
        if not name:
            errors.append("%s is missing a 'name'." % where)

        category = m.get("category")
        if not category:
            errors.append("%s is missing a 'category'." % where)
        elif category not in category_ids:
            errors.append("%s has unknown category '%s'." % (where, category))

        for element in m.get("elements", []):
            if slug(element) not in elements:
                errors.append("%s lists element '%s', which is not in the elements list." % (where, element))

        if not isinstance(m.get("abilities", []), list):
            errors.append("%s 'abilities' must be a list." % where)
        if not isinstance(m.get("found_at", []), list):
            errors.append("%s 'found_at' must be a list." % where)
        elif not m.get("found_at"):
            errors.append("%s has no 'found_at' location." % where)

    for i, combo in enumerate(data.get("combos", [])):
        where = "combo #%d" % (i + 1)
        support = combo.get("support")
        target = combo.get("target")
        if support not in materia_ids:
            errors.append("%s points at unknown support materia '%s'." % (where, support))
        if target not in materia_ids:
            errors.append("%s points at unknown target materia '%s'." % (where, target))
        if not combo.get("effect"):
            errors.append("%s is missing an 'effect' description." % where)

    return errors
