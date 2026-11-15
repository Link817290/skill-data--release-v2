import argparse,calendar,datetime as dt
def due(day,months=1):
    if not isinstance(months,int) or months<0:raise ValueError('Nonnegative whole months required')
    n=day.year*12+day.month-1+months;y,m=divmod(n,12);m+=1
    return day.replace(year=y,month=m,day=min(day.day,calendar.monthrange(y,m)[1]))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('date');p.add_argument('--months',type=int,default=1);a=p.parse_args();print(due(dt.date.fromisoformat(a.date),a.months))
