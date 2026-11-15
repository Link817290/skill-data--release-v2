"""Stable, role-separated IDs over the unchanged visible document text."""


def blocks_from_text(text, role='candidate'):
    prefixes = {'candidate': 'cand', 'reference': 'ref'}
    if role not in prefixes:
        raise ValueError('Unknown document evidence role')
    return [{'id': f'{prefixes[role]}-{i:04d}', 'text': line}
            for i, line in enumerate(text.splitlines(), 1) if line.strip()]
