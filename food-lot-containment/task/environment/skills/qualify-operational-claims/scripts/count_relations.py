"""Count products and product-channel relationships with explicit keys."""
import argparse,json
from pathlib import Path
def counts(rows,product_fields,channel_field):
    if not product_fields or channel_field in product_fields:raise ValueError('Use separate product and channel keys')
    products=set();relations=set();channels=set()
    for row in rows:
        fields=product_fields+[channel_field]
        if any(row.get(f) is None or str(row[f]).strip()=='' for f in fields):raise ValueError('Incomplete key; resolve or separate unknown records')
        key=tuple(str(row[f]).strip() for f in product_fields);channel=str(row[channel_field]).strip()
        products.add(key);relations.add((key,channel));channels.add(channel)
    return dict(rows=len(rows),products=len(products),relationships=len(relations),channels=len(channels))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--product-fields',nargs='+',required=True);p.add_argument('--channel-field',required=True);a=p.parse_args()
    print(json.dumps(counts(json.loads(a.input.read_text(encoding='utf-8')),a.product_fields,a.channel_field)))
