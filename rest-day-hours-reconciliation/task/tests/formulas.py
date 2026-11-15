"""Evaluate the submitted time formulas with a restricted Excel token grammar."""

import datetime as dt
import math
from decimal import Decimal, ROUND_HALF_UP

from openpyxl.formula import Tokenizer
from openpyxl.utils.datetime import to_excel


def numeric(value):
    if isinstance(value, dt.time):
        return (value.hour * 3600 + value.minute * 60 + value.second) / 86400
    if isinstance(value, (dt.datetime, dt.date)):
        return to_excel(value)
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    raise ValueError('Non-numeric operand')


def evaluate(sheet, cached, cell, trail=()):
    value = cell.value
    if not isinstance(value, str) or not value.startswith('='):
        return value
    identity = (sheet.title, cell.coordinate)
    if identity in trail or len(trail) > 30:
        return None
    tokens = [t for t in Tokenizer(value).items if t.type != 'WHITE-SPACE']
    cursor = 0
    precedence = {'=': 1, '<>': 1, '<': 1, '>': 1, '<=': 1, '>=': 1,
                  '+': 2, '-': 2, '*': 3, '/': 3, '^': 4}

    def expression(minimum=0):
        nonlocal cursor
        token = tokens[cursor]
        cursor += 1
        if token.type == 'OPERATOR-PREFIX':
            result = numeric(expression(4)) * (-1 if token.value == '-' else 1)
        elif token.type == 'PAREN' and token.subtype == 'OPEN':
            result = expression()
            if tokens[cursor].subtype != 'CLOSE':
                raise ValueError('Unclosed parenthesis')
            cursor += 1
        elif token.type == 'FUNC' and token.subtype == 'OPEN':
            args = []
            while not (tokens[cursor].type == 'FUNC' and tokens[cursor].subtype == 'CLOSE'):
                args.append(expression())
                if tokens[cursor].type == 'SEP':
                    cursor += 1
                elif tokens[cursor].subtype != 'CLOSE':
                    raise ValueError('Invalid argument separator')
            cursor += 1
            name = token.value[:-1].upper().removeprefix('_XLFN.')
            if name == 'ROUND':
                result = float(Decimal(str(numeric(args[0]))).quantize(
                    Decimal(1).scaleb(-int(numeric(args[1]))), rounding=ROUND_HALF_UP))
            elif name == 'MOD':
                result = numeric(args[0]) % numeric(args[1])
            elif name == 'TIMEVALUE':
                parsed = dt.time.fromisoformat(str(args[0]))
                result = numeric(parsed)
            elif name == 'TIME':
                result = (numeric(args[0]) * 3600 + numeric(args[1]) * 60 + numeric(args[2])) % 86400 / 86400
            elif name == 'IF':
                result = args[1] if args[0] else args[2]
            elif name == 'OR':
                result = any(bool(a) for a in args)
            elif name == 'AND':
                result = all(bool(a) for a in args)
            elif name in {'SUM', 'MIN', 'MAX', 'ABS'}:
                values = [numeric(a) for a in args]
                result = {'SUM': sum, 'MIN': min, 'MAX': max, 'ABS': lambda a: abs(a[0])}[name](values)
            else:
                raise ValueError('Unsupported Excel function: ' + name)
        elif token.type == 'OPERAND':
            if token.subtype == 'NUMBER':
                result = float(token.value)
            elif token.subtype == 'TEXT':
                result = token.value[1:-1].replace('""', '"')
            elif token.subtype == 'LOGICAL':
                result = token.value.upper() == 'TRUE'
            elif token.subtype == 'RANGE':
                ref = token.value.replace('$', '')
                ref_sheet = sheet
                if '!' in ref:
                    title, ref = ref.rsplit('!', 1)
                    ref_sheet = sheet.parent[title.strip("'").replace("''", "'")]
                if ':' in ref or '[' in ref:
                    raise ValueError('Unsupported range operand')
                result = evaluate(ref_sheet, cached.parent[ref_sheet.title], ref_sheet[ref], trail + (identity,))
            else:
                raise ValueError('Unsupported operand')
        else:
            raise ValueError('Unsupported token')
        while cursor < len(tokens):
            operation = tokens[cursor]
            if operation.type == 'OPERATOR-POSTFIX' and operation.value == '%':
                result = numeric(result) / 100
                cursor += 1
                continue
            if operation.type != 'OPERATOR-INFIX' or precedence.get(operation.value, -1) < minimum:
                break
            cursor += 1
            right = expression(precedence[operation.value] + 1)
            op = operation.value
            if op in {'=', '<>', '<', '>', '<=', '>='}:
                result = {'=': lambda: result == right, '<>': lambda: result != right,
                          '<': lambda: result < right, '>': lambda: result > right,
                          '<=': lambda: result <= right, '>=': lambda: result >= right}[op]()
            else:
                left, right = numeric(result), numeric(right)
                result = {'+': lambda: left + right, '-': lambda: left - right,
                          '*': lambda: left * right, '/': lambda: left / right,
                          '^': lambda: left ** right}[op]()
        return result

    try:
        result = expression()
        if cursor != len(tokens):
            raise ValueError('Trailing formula tokens')
        return result
    except (ValueError, IndexError, KeyError, TypeError, ZeroDivisionError, OverflowError):
        return cached[cell.coordinate].value
