from __future__ import annotations
from typing import Sequence
from ..data import data_ops as e


def find_all_subtypes_of_tp_in_schema(
    schema: e.DBSchema, tp: e.QualifiedName
) -> Sequence[e.QualifiedName]:
    checked_tps_set = set()  # Keeps fast lookup for visited nodes
    checked_tps = []  # Maintains original order for return value
    frontier = [tp]

    # Build a reverse mapping: {supertype: [subtype list]}
    # This lets us quickly find all direct subtypes of any type.
    # Precompute because repeated nested lookups are extremely expensive.
    super_to_sub = {}
    for subtype, supertypes in schema.subtyping_relations.items():
        for supertype in supertypes:
            if supertype not in super_to_sub:
                super_to_sub[supertype] = []
            super_to_sub[supertype].append(subtype)

    while frontier:
        next_tp = frontier.pop()
        if next_tp in checked_tps_set:
            continue
        checked_tps_set.add(next_tp)
        checked_tps.append(next_tp)

        # Add direct subtypes to the frontier
        subtypes = super_to_sub.get(next_tp)
        if subtypes:
            frontier.extend(subtypes)

    return checked_tps


def find_all_supertypes_of_tp_in_schema(
    schema: e.DBSchema, tp: e.QualifiedName
) -> Sequence[e.QualifiedName]:
    checked_tps = []
    frontier = [tp]

    while len(frontier) > 0:
        next_tp = frontier.pop()
        if next_tp in checked_tps:
            continue
        checked_tps.append(next_tp)
        frontier.extend(schema.subtyping_relations[next_tp])

    return checked_tps
