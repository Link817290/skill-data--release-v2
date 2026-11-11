import argparse,json,math
def convert(mm,density,maximum):
    if not all(math.isfinite(x) and x>0 for x in (mm,density,maximum)):raise ValueError('Finite positive inputs required')
    raw=mm*density
    return {'requested_units':raw,'within_limit':raw<=maximum,'maximum_mm':maximum/density,'integral_units':raw.is_integer()}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mm',type=float,required=True);p.add_argument('--density',type=float,required=True);p.add_argument('--maximum',type=float,required=True);a=p.parse_args();print(json.dumps(convert(a.mm,a.density,a.maximum)))
