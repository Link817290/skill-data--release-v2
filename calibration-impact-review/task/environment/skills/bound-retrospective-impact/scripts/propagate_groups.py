"""Propagate supplied links; completeness requires separate documented coverage."""
def affected_items(failed_groups,links,documented_complete_groups=None):
    groups=set(failed_groups);known=set();invalid=set()
    documented=set(documented_complete_groups or [])
    for link in links:
        group=link["group"];item=link.get("item")
        if group in groups:
            if item is not None and str(item).strip():known.add(str(item))
            else:invalid.add(group)
    unresolved=(groups-documented)|invalid
    return {"known_items":sorted(known),"unresolved_groups":sorted(unresolved,key=str),"complete":not unresolved}
