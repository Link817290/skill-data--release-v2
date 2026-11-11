#!/usr/bin/env python3
"""Build the reference planning workbook directly from the supplied source workbook."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pulp
from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.table import Table, TableStyleInfo


SOURCE_NAME = "Supply chain logisitcs problem.xlsx"
OUTPUT_NAME = "network_design_recommendation.xlsx"


@dataclass(frozen=True)
class Order:
    index: int
    source_row: int
    order_id: str
    customer: str
    product: str
    service: str
    quantity: float
    weight: float
    destination_port: str


@dataclass(frozen=True)
class Route:
    source_row: int | None
    origin_port: str
    carrier: str
    service: str
    mode: str
    minimum_weight: float | None
    maximum_weight: float | None
    minimum_charge: float
    rate: float
    transit_days: float | None
    freight_cost: float


@dataclass(frozen=True)
class Option:
    plant: str
    route: Route
    warehouse_cost: float

    @property
    def total_cost(self) -> float:
        return self.warehouse_cost + self.route.freight_cost


def scalar_id(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (int, float)):
        text = format(Decimal(str(value)).normalize(), "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    return str(value).strip()


def rows_by_header(path: Path, sheet: str) -> tuple[list[str], list[dict[str, Any]]]:
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    iterator = ws.iter_rows(values_only=True)
    headers = [str(v).strip() if v is not None else "" for v in next(iterator)]
    rows: list[dict[str, Any]] = []
    for source_row, values in enumerate(iterator, start=2):
        if not any(v is not None for v in values):
            continue
        record = {headers[i]: values[i] for i in range(min(len(headers), len(values))) if headers[i]}
        record["__source_row__"] = source_row
        rows.append(record)
    wb.close()
    return headers, rows


def load_problem(source: Path) -> dict[str, Any]:
    _, raw_orders = rows_by_header(source, "OrderList")
    _, raw_rates = rows_by_header(source, "FreightRates")
    _, raw_costs = rows_by_header(source, "WhCosts")
    _, raw_caps = rows_by_header(source, "WhCapacities")
    _, raw_products = rows_by_header(source, "ProductsPerPlant")
    _, raw_vmi = rows_by_header(source, "VmiCustomers")
    _, raw_ports = rows_by_header(source, "PlantPorts")

    orders = [
        Order(
            index=i,
            source_row=int(r["__source_row__"]),
            order_id=scalar_id(r["Order ID"]),
            customer=scalar_id(r["Customer"]),
            product=scalar_id(r["Product ID"]),
            service=scalar_id(r["Service Level"]).upper(),
            quantity=float(r["Unit quantity"]),
            weight=float(r["Weight"]),
            destination_port=scalar_id(r["Destination Port"]),
        )
        for i, r in enumerate(raw_orders)
    ]

    capacities = {scalar_id(r["Plant ID"]): int(r["Daily Capacity"]) for r in raw_caps}
    unit_costs = {scalar_id(r["WH"]): float(r["Cost/unit"]) for r in raw_costs}
    plants = sorted(set(capacities) & set(unit_costs))

    product_plants: dict[str, set[str]] = defaultdict(set)
    for r in raw_products:
        plant = scalar_id(r["Plant Code"])
        if plant in plants:
            product_plants[scalar_id(r["Product ID"])].add(plant)

    plant_ports: dict[str, set[str]] = defaultdict(set)
    for r in raw_ports:
        plant = scalar_id(r["Plant Code"])
        if plant in plants:
            plant_ports[plant].add(scalar_id(r["Port"]))

    restricted_customers: dict[str, set[str]] = defaultdict(set)
    for r in raw_vmi:
        plant = scalar_id(r["Plant Code"])
        if plant in plants:
            restricted_customers[plant].add(scalar_id(r["Customers"]))

    air_rates: list[dict[str, Any]] = []
    for r in raw_rates:
        if scalar_id(r["mode_dsc"]).upper() != "AIR":
            continue
        air_rates.append(
            {
                "source_row": int(r["__source_row__"]),
                "carrier": scalar_id(r["Carrier"]),
                "origin": scalar_id(r["orig_port_cd"]),
                "destination": scalar_id(r["dest_port_cd"]),
                "minimum_weight": float(r["minm_wgh_qty"]),
                "maximum_weight": float(r["max_wgh_qty"]),
                "service": scalar_id(r["svc_cd"]).upper(),
                "minimum_charge": float(r["minimum cost"]),
                "rate": float(r["rate"]),
                "transit_days": float(r["tpt_day_cnt"]),
            }
        )

    return {
        "orders": orders,
        "plants": plants,
        "capacities": capacities,
        "unit_costs": unit_costs,
        "product_plants": product_plants,
        "plant_ports": plant_ports,
        "restricted_customers": restricted_customers,
        "air_rates": air_rates,
        "source_counts": {
            "OrderList": len(raw_orders),
            "FreightRates": len(raw_rates),
            "WhCosts": len(raw_costs),
            "WhCapacities": len(raw_caps),
            "ProductsPerPlant": len(raw_products),
            "VmiCustomers": len(raw_vmi),
            "PlantPorts": len(raw_ports),
        },
    }


def cheapest_route(problem: dict[str, Any], order: Order, plant: str) -> Route | None:
    ports = problem["plant_ports"].get(plant, set())
    if not ports:
        return None
    if order.service == "CRF":
        return Route(
            source_row=None,
            origin_port=sorted(ports)[0],
            carrier="CUSTOMER",
            service="CRF",
            mode="CUSTOMER",
            minimum_weight=None,
            maximum_weight=None,
            minimum_charge=0.0,
            rate=0.0,
            transit_days=None,
            freight_cost=0.0,
        )

    candidates: list[Route] = []
    for rate_row in problem["air_rates"]:
        if rate_row["origin"] not in ports:
            continue
        if rate_row["destination"] != order.destination_port:
            continue
        if rate_row["service"] != order.service:
            continue
        if not rate_row["minimum_weight"] <= order.weight <= rate_row["maximum_weight"]:
            continue
        freight_cost = max(rate_row["minimum_charge"], rate_row["rate"] * order.weight)
        candidates.append(
            Route(
                source_row=rate_row["source_row"],
                origin_port=rate_row["origin"],
                carrier=rate_row["carrier"],
                service=rate_row["service"],
                mode="AIR",
                minimum_weight=rate_row["minimum_weight"],
                maximum_weight=rate_row["maximum_weight"],
                minimum_charge=rate_row["minimum_charge"],
                rate=rate_row["rate"],
                transit_days=rate_row["transit_days"],
                freight_cost=freight_cost,
            )
        )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda r: (
            round(r.freight_cost, 9),
            r.transit_days if r.transit_days is not None else 10**9,
            r.carrier,
            r.origin_port,
            r.source_row or 0,
        ),
    )


def build_options(problem: dict[str, Any]) -> tuple[dict[tuple[int, str], Option], dict[int, list[str]]]:
    options: dict[tuple[int, str], Option] = {}
    eligible_by_order: dict[int, list[str]] = defaultdict(list)
    restricted = problem["restricted_customers"]
    for order in problem["orders"]:
        for plant in sorted(problem["product_plants"].get(order.product, set())):
            if plant in restricted and order.customer not in restricted[plant]:
                continue
            route = cheapest_route(problem, order, plant)
            if route is None:
                continue
            option = Option(
                plant=plant,
                route=route,
                warehouse_cost=order.quantity * problem["unit_costs"][plant],
            )
            options[(order.index, plant)] = option
            eligible_by_order[order.index].append(plant)
    return options, eligible_by_order


def solve_assignment(
    problem: dict[str, Any],
    options: dict[tuple[int, str], Option],
    *,
    unavailable: str | None = None,
    minimize_facilities: bool = False,
) -> tuple[dict[int, Option], int, float, int]:
    by_order: dict[int, list[tuple[int, str]]] = defaultdict(list)
    by_plant: dict[str, list[tuple[int, str]]] = defaultdict(list)
    active_options = {
        key: option for key, option in options.items() if key[1] != unavailable
    }
    for key in active_options:
        by_order[key[0]].append(key)
        by_plant[key[1]].append(key)

    label = unavailable or "primary"
    model = pulp.LpProblem(f"current_day_network_{label}", pulp.LpMaximize)
    variables = {
        key: pulp.LpVariable(f"assign_{key[0]}_{key[1]}", lowBound=0, upBound=1)
        for key in active_options
    }
    facility_used = {
        plant: pulp.LpVariable(f"use_{plant}", lowBound=0, upBound=1, cat="Binary")
        for plant in problem["plants"]
        if plant != unavailable and by_plant.get(plant)
    }
    model += pulp.lpSum(variables.values())
    for keys in by_order.values():
        model += pulp.lpSum(variables[key] for key in keys) <= 1
    for plant, keys in by_plant.items():
        model += (
            pulp.lpSum(variables[key] for key in keys)
            <= problem["capacities"][plant] * facility_used[plant]
        )
        model += facility_used[plant] <= pulp.lpSum(variables[key] for key in keys)

    status = model.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=300))
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(f"maximum-service solve failed: {pulp.LpStatus[status]}")
    maximum_service = int(round(float(pulp.value(model.objective))))

    if minimize_facilities:
        model.sense = pulp.LpMinimize
        model.setObjective(pulp.lpSum(facility_used.values()))
        model += pulp.lpSum(variables.values()) == maximum_service
        status = model.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=300))
        if pulp.LpStatus[status] != "Optimal":
            raise RuntimeError(f"minimum-footprint solve failed: {pulp.LpStatus[status]}")
        minimum_facilities = int(round(float(pulp.value(model.objective))))
        model += pulp.lpSum(facility_used.values()) == minimum_facilities
    else:
        minimum_facilities = 0
        model += pulp.lpSum(variables.values()) == maximum_service

    model.sense = pulp.LpMinimize
    model.setObjective(
        pulp.lpSum(variables[key] * active_options[key].total_cost for key in active_options)
    )
    status = model.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=300))
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(f"minimum-cost solve failed: {pulp.LpStatus[status]}")

    assigned: dict[int, Option] = {}
    for key, variable in variables.items():
        value = float(variable.value() or 0.0)
        if 1e-7 < value < 1 - 1e-7:
            raise RuntimeError(f"non-integral assignment for {key}: {value}")
        if value >= 0.5:
            assigned[key[0]] = active_options[key]
    reference_cost = sum(option.total_cost for option in assigned.values())
    used_count = len({option.plant for option in assigned.values()})
    if minimize_facilities and used_count != minimum_facilities:
        raise RuntimeError("published flow does not use the minimum facility count")
    return assigned, maximum_service, reference_cost, used_count


NAVY = "16324F"
TEAL = "087E8B"
PALE_BLUE = "D9EAF7"
PALE_GREEN = "E2F0D9"
PALE_RED = "FCE4D6"
PALE_YELLOW = "FFF2CC"
WHITE = "FFFFFF"
GRID = Side(style="thin", color="D9E1F2")


def title_row(ws, title: str, subtitle: str, end_column: int) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=end_column)
    ws.cell(1, 1, title)
    ws.cell(1, 1).font = Font(size=18, bold=True, color=WHITE)
    ws.cell(1, 1).fill = PatternFill("solid", fgColor=NAVY)
    ws.cell(1, 1).alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 30
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=end_column)
    ws.cell(2, 1, subtitle)
    ws.cell(2, 1).font = Font(size=10, italic=True, color="44546A")
    ws.cell(2, 1).alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[2].height = 30


def header_style(ws, row: int, start: int, end: int) -> None:
    for cell in ws.iter_cols(min_col=start, max_col=end, min_row=row, max_row=row):
        c = cell[0]
        c.font = Font(bold=True, color=WHITE)
        c.fill = PatternFill("solid", fgColor=TEAL)
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = Border(bottom=GRID)
    ws.row_dimensions[row].height = 32


def add_table(ws, name: str, ref: str) -> None:
    table = Table(displayName=name, ref=ref)
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    ws.add_table(table)


def set_widths(ws, widths: dict[str, float]) -> None:
    for column, width in widths.items():
        ws.column_dimensions[column].width = width


def build_workbook(
    problem: dict[str, Any],
    options: dict[tuple[int, str], Option],
    eligible_by_order: dict[int, list[str]],
    assigned: dict[int, Option],
    outage_results: list[tuple[str, dict[int, Option], int, float, int]],
    governing_outage: tuple[str, dict[int, Option], int, float, int],
    output: Path,
) -> None:
    wb = Workbook()
    default = wb.active
    wb.remove(default)
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.calculation.calcMode = "auto"
    wb.properties.creator = "Operations Planning"
    wb.properties.title = "Current-day distribution center network recommendation"
    wb.properties.subject = "Facility use, order allocation, capacity, cost, and exceptions"

    allocation_name = "Order Allocation"
    facility_name = "Facility Plan"

    ws = wb.create_sheet("Executive Summary")
    title_row(
        ws,
        "Current-day distribution center network recommendation",
        "Formula-based decision view. Detailed assignments remain the controlling record.",
        5,
    )
    summary_rows = [
        ("Planning scope", "Current-day facility use and order allocation"),
        ("Demand orders", f"=COUNTA('{allocation_name}'!$A:$A)-1"),
        ("Assigned orders", f'=COUNTIF(\'{allocation_name}\'!$H:$H,"ASSIGNED")'),
        ("Unassigned orders", f'=COUNTIF(\'{allocation_name}\'!$H:$H,"UNASSIGNED")'),
        ("Service rate", "=IFERROR(B6/B5,0)"),
        ("Total stated daily capacity", f"=SUM('{facility_name}'!$D$2:$D$20)"),
        ("Facilities used", f'=COUNTIF(\'{facility_name}\'!$B$2:$B$20,"USE")'),
        ("Warehouse variable cost", f"=SUM('{allocation_name}'!$S:$S)"),
        ("Company freight cost", f"=SUM('{allocation_name}'!$T:$T)"),
        ("Total variable cost", f"=SUM('{allocation_name}'!$U:$U)"),
        ("Company-arranged mode", "AIR"),
        ("Customer-arranged service", "CRF; company freight cost remains zero"),
        ("Primary facilities used", f'=COUNTIF(\'{facility_name}\'!$B$2:$B$20,"USE")'),
        ("Single-facility outages screened", "=COUNTA('Outage Screening'!$A:$A)-1"),
        ("Governing outage", governing_outage[0]),
        ("Governing-outage recoverable orders", governing_outage[2]),
        (
            "Decision boundary",
            "Use/non-use is a current-day operating decision. Recovery may use another current facility, but permanent closure or greenfield location is not supported by the supplied economics.",
        ),
    ]
    ws.append([None])
    for label, value in summary_rows:
        ws.append([label, value])
    header_style(ws, 3, 1, 2)
    ws["A3"] = "Decision measure"
    ws["B3"] = "Result or boundary"
    ws["B8"].number_format = "0.0%"
    for row in range(4, ws.max_row + 1):
        ws.cell(row, 1).font = Font(bold=True, color=NAVY)
        ws.cell(row, 1).fill = PatternFill("solid", fgColor=PALE_BLUE)
        ws.cell(row, 1).border = Border(bottom=GRID)
        ws.cell(row, 2).border = Border(bottom=GRID)
        ws.cell(row, 2).alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A4"
    set_widths(ws, {"A": 30, "B": 92, "C": 14, "D": 14, "E": 14})

    plant_assigned: dict[str, int] = defaultdict(int)
    plant_eligible: dict[str, int] = defaultdict(int)
    ordered_products = {order.product for order in problem["orders"]}
    plant_ordered_products: dict[str, set[str]] = defaultdict(set)
    for order in problem["orders"]:
        for plant in eligible_by_order.get(order.index, []):
            plant_eligible[plant] += 1
        if order.index in assigned:
            plant_assigned[assigned[order.index].plant] += 1
    for product in ordered_products:
        for plant in problem["product_plants"].get(product, set()):
            plant_ordered_products[plant].add(product)

    ws = wb.create_sheet(facility_name)
    headers = [
        "Facility",
        "Current-day decision",
        "Assigned order count",
        "Daily capacity",
        "Utilization",
        "Cost per unit",
        "Eligible order pool",
        "Restricted-customer facility",
        "Supported ports",
        "Decision evidence",
    ]
    ws.append(headers)
    for row_index, plant in enumerate(problem["plants"], start=2):
        used = plant_assigned[plant] > 0
        if used:
            evidence = "Positive valid order flow in the current-day allocation"
        elif not plant_ordered_products.get(plant):
            evidence = "No supplied ordered-product mapping closes to this facility"
        elif not plant_eligible.get(plant):
            evidence = "No current-day order closes every supplied eligibility relation"
        else:
            evidence = "Not selected after maximum service, minimum operating footprint, and variable-cost tie-break"
        ws.append(
            [
                plant,
                "USE" if used else "NOT USED - CURRENT DAY",
                f'=COUNTIF(\'{allocation_name}\'!$I:$I,A{row_index})',
                problem["capacities"][plant],
                f"=IFERROR(C{row_index}/D{row_index},0)",
                problem["unit_costs"][plant],
                plant_eligible.get(plant, 0),
                "YES" if plant in problem["restricted_customers"] else "NO",
                ", ".join(sorted(problem["plant_ports"].get(plant, set()))),
                evidence,
            ]
        )
    header_style(ws, 1, 1, len(headers))
    add_table(ws, "FacilityPlanTable", f"A1:J{ws.max_row}")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:J{ws.max_row}"
    for row in range(2, ws.max_row + 1):
        ws.cell(row, 5).number_format = "0.0%"
        ws.cell(row, 6).number_format = "$0.0000"
        ws.cell(row, 10).alignment = Alignment(wrap_text=True, vertical="top")
    ws.conditional_formatting.add(
        f"B2:B{ws.max_row}", FormulaRule(formula=['LEFT(B2,3)="USE"'], fill=PatternFill("solid", fgColor=PALE_GREEN))
    )
    set_widths(ws, {"A": 14, "B": 25, "C": 18, "D": 15, "E": 13, "F": 15, "G": 18, "H": 26, "I": 20, "J": 58})

    ws = wb.create_sheet(allocation_name)
    headers = [
        "Order ID",
        "Source order row",
        "Customer",
        "Product ID",
        "Service level",
        "Unit quantity",
        "Weight",
        "Decision",
        "Facility",
        "Origin port",
        "Carrier",
        "Mode",
        "Rate source row",
        "Rate minimum weight",
        "Rate maximum weight",
        "Minimum charge",
        "Rate per kg",
        "Transit days",
        "Warehouse cost",
        "Freight cost",
        "Total variable cost",
        "Eligible facility count",
        "Exception class",
        "Evidence note",
    ]
    ws.append(headers)
    for excel_row, order in enumerate(problem["orders"], start=2):
        option = assigned.get(order.index)
        if option is None:
            reason = "STRUCTURAL - NO ELIGIBLE PATH" if not eligible_by_order.get(order.index) else "CAPACITY - DISPLACED"
            ws.append(
                [
                    order.order_id,
                    order.source_row,
                    order.customer,
                    order.product,
                    order.service,
                    order.quantity,
                    order.weight,
                    "UNASSIGNED",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    0,
                    0,
                    None,
                    0,
                    0,
                    0,
                    len(eligible_by_order.get(order.index, [])),
                    reason,
                    "No current assignment is claimed; see exception class and facility capacity context.",
                ]
            )
        else:
            route = option.route
            ws.append(
                [
                    order.order_id,
                    order.source_row,
                    order.customer,
                    order.product,
                    order.service,
                    order.quantity,
                    order.weight,
                    "ASSIGNED",
                    option.plant,
                    route.origin_port,
                    route.carrier,
                    route.mode,
                    route.source_row,
                    route.minimum_weight,
                    route.maximum_weight,
                    route.minimum_charge,
                    route.rate,
                    route.transit_days,
                    f'=IF(H{excel_row}="ASSIGNED",F{excel_row}*INDEX(\'{facility_name}\'!$F$2:$F$20,MATCH(I{excel_row},\'{facility_name}\'!$A$2:$A$20,0)),0)',
                    f'=IF(OR(H{excel_row}<>"ASSIGNED",E{excel_row}="CRF"),0,MAX(P{excel_row},Q{excel_row}*G{excel_row}))',
                    f"=S{excel_row}+T{excel_row}",
                    len(eligible_by_order[order.index]),
                    None,
                    f"OrderList row {order.source_row}; current relationship and rate records support the selected path.",
                ]
            )
    header_style(ws, 1, 1, len(headers))
    add_table(ws, "OrderAllocationTable", f"A1:X{ws.max_row}")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:X{ws.max_row}"
    for row in range(2, ws.max_row + 1):
        for col in (6, 7, 14, 15, 16, 17, 19, 20, 21):
            ws.cell(row, col).number_format = "$#,##0.00" if col in (16, 19, 20, 21) else "0.00"
        ws.cell(row, 24).alignment = Alignment(wrap_text=True, vertical="top")
    ws.conditional_formatting.add(
        f"H2:H{ws.max_row}", FormulaRule(formula=['H2="ASSIGNED"'], fill=PatternFill("solid", fgColor=PALE_GREEN))
    )
    ws.conditional_formatting.add(
        f"H2:H{ws.max_row}", FormulaRule(formula=['H2="UNASSIGNED"'], fill=PatternFill("solid", fgColor=PALE_RED))
    )
    set_widths(
        ws,
        {
            "A": 18, "B": 15, "C": 24, "D": 14, "E": 14, "F": 14,
            "G": 12, "H": 15, "I": 14, "J": 14, "K": 14, "L": 12,
            "M": 16, "N": 18, "O": 18, "P": 15, "Q": 13, "R": 13,
            "S": 17, "T": 15, "U": 19, "V": 19, "W": 30, "X": 72,
        },
    )

    ws = wb.create_sheet("Exceptions")
    headers = ["Order ID", "Customer", "Product ID", "Service level", "Eligible facility count", "Exception class", "Decision consequence"]
    ws.append(headers)
    for order in problem["orders"]:
        if order.index in assigned:
            continue
        ws.append(
            [
                order.order_id,
                order.customer,
                order.product,
                order.service,
                len(eligible_by_order.get(order.index, [])),
                "STRUCTURAL - NO ELIGIBLE PATH" if not eligible_by_order.get(order.index) else "CAPACITY - DISPLACED",
                "Remain unassigned unless a supplied constraint or available capacity changes.",
            ]
        )
    header_style(ws, 1, 1, len(headers))
    add_table(ws, "ExceptionTable", f"A1:G{ws.max_row}")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:G{ws.max_row}"
    set_widths(ws, {"A": 18, "B": 25, "C": 14, "D": 14, "E": 22, "F": 30, "G": 66})

    ws = wb.create_sheet("Outage Screening")
    outage_headers = [
        "Outaged facility",
        "Primary facility",
        "Maximum recoverable orders",
        "Recovery unassigned orders",
        "Minimum recovery variable cost",
        "Service retained versus primary",
        "No remaining path orders",
        "Remaining path but no capacity orders",
        "Governing outage",
        "Decision evidence",
    ]
    ws.append(outage_headers)
    primary_count = len(assigned)
    for outaged, recovery, recoverable, recovery_cost, _used_count in outage_results:
        row_index = ws.max_row + 1
        structural_count = sum(
            1 for order in problem["orders"]
            if not [plant for plant in eligible_by_order.get(order.index, []) if plant != outaged]
        )
        capacity_count = len(problem["orders"]) - recoverable - structural_count
        ws.append(
            [
                outaged,
                "YES",
                recoverable,
                len(problem["orders"]) - recoverable,
                recovery_cost,
                f"=C{row_index}/{primary_count}",
                structural_count,
                capacity_count,
                "YES" if outaged == governing_outage[0] else "NO",
                "Single-facility capacity removed before maximizing recoverable service; variable cost is minimized only at that service level.",
            ]
        )
    header_style(ws, 1, 1, len(outage_headers))
    add_table(ws, "OutageScreeningTable", f"A1:J{ws.max_row}")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:J{ws.max_row}"
    for row in range(2, ws.max_row + 1):
        ws.cell(row, 5).number_format = "$#,##0.00"
        ws.cell(row, 6).number_format = "0.0%"
        ws.cell(row, 10).alignment = Alignment(wrap_text=True, vertical="top")
    set_widths(ws, {"A": 20, "B": 17, "C": 27, "D": 27, "E": 30, "F": 28, "G": 26, "H": 36, "I": 20, "J": 76})

    outage_allocation_name = "Governing Outage Allocation"
    ws = wb.create_sheet(outage_allocation_name)
    outage_headers = [
        "Order ID",
        "Source order row",
        "Customer",
        "Product ID",
        "Service level",
        "Unit quantity",
        "Weight",
        "Decision",
        "Facility",
        "Origin port",
        "Carrier",
        "Mode",
        "Rate source row",
        "Rate minimum weight",
        "Rate maximum weight",
        "Minimum charge",
        "Rate per kg",
        "Transit days",
        "Warehouse cost",
        "Freight cost",
        "Total variable cost",
        "Eligible facility count",
        "Exception class",
        "Outaged facility",
        "Evidence note",
    ]
    ws.append(outage_headers)
    outage_plant, recovery_assigned, _recoverable, _recovery_cost, _recovery_used = governing_outage
    for excel_row, order in enumerate(problem["orders"], start=2):
        option = recovery_assigned.get(order.index)
        recovery_eligible = [plant for plant in eligible_by_order.get(order.index, []) if plant != outage_plant]
        if option is None:
            reason = "STRUCTURAL - NO ELIGIBLE PATH" if not recovery_eligible else "CAPACITY - DISPLACED"
            ws.append(
                [
                    order.order_id, order.source_row, order.customer, order.product, order.service,
                    order.quantity, order.weight, "UNASSIGNED", None, None, None, None, None,
                    None, None, 0, 0, None, 0, 0, 0, len(recovery_eligible), reason,
                    outage_plant,
                    "No recovery assignment is claimed; the outaged facility is removed from current eligibility before capacity allocation.",
                ]
            )
        else:
            route = option.route
            ws.append(
                [
                    order.order_id, order.source_row, order.customer, order.product, order.service,
                    order.quantity, order.weight, "ASSIGNED", option.plant, route.origin_port,
                    route.carrier, route.mode, route.source_row, route.minimum_weight,
                    route.maximum_weight, route.minimum_charge, route.rate, route.transit_days,
                    f'=IF(H{excel_row}="ASSIGNED",F{excel_row}*INDEX(\'Governing Outage Facility\'!$F$2:$F$20,MATCH(I{excel_row},\'Governing Outage Facility\'!$A$2:$A$20,0)),0)',
                    f'=IF(OR(H{excel_row}<>"ASSIGNED",E{excel_row}="CRF"),0,MAX(P{excel_row},Q{excel_row}*G{excel_row}))',
                    f"=S{excel_row}+T{excel_row}", len(recovery_eligible), None, outage_plant,
                    f"OrderList row {order.source_row}; recovery path excludes {outage_plant} and retains current relationship and tariff evidence.",
                ]
            )
    header_style(ws, 1, 1, len(outage_headers))
    add_table(ws, "GoverningOutageAllocationTable", f"A1:Y{ws.max_row}")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:Y{ws.max_row}"
    for row in range(2, ws.max_row + 1):
        for col in (6, 7, 14, 15, 16, 17, 19, 20, 21):
            ws.cell(row, col).number_format = "$#,##0.00" if col in (16, 19, 20, 21) else "0.00"
        ws.cell(row, 25).alignment = Alignment(wrap_text=True, vertical="top")
    set_widths(ws, {"A": 18, "B": 15, "C": 24, "D": 14, "E": 14, "F": 14, "G": 12, "H": 15, "I": 14, "J": 14, "K": 14, "L": 12, "M": 16, "N": 18, "O": 18, "P": 15, "Q": 13, "R": 13, "S": 17, "T": 15, "U": 19, "V": 19, "W": 30, "X": 18, "Y": 72})

    ws = wb.create_sheet("Governing Outage Facility")
    facility_headers = [
        "Facility", "Recovery decision", "Assigned order count", "Available daily capacity",
        "Utilization", "Cost per unit", "Outaged facility", "Decision evidence",
    ]
    ws.append(facility_headers)
    recovery_flow: dict[str, int] = defaultdict(int)
    for option in recovery_assigned.values():
        recovery_flow[option.plant] += 1
    for row_index, plant in enumerate(problem["plants"], start=2):
        available_capacity = 0 if plant == outage_plant else problem["capacities"][plant]
        decision = "UNAVAILABLE" if plant == outage_plant else ("USE" if recovery_flow[plant] else "NOT USED - RECOVERY")
        ws.append(
            [
                plant, decision,
                f'=COUNTIF(\'{outage_allocation_name}\'!$I:$I,A{row_index})',
                available_capacity,
                f"=IFERROR(C{row_index}/D{row_index},0)", problem["unit_costs"][plant],
                outage_plant,
                "Capacity is zero in this scenario" if plant == outage_plant else "Status follows valid governing-outage recovery flow",
            ]
        )
    header_style(ws, 1, 1, len(facility_headers))
    add_table(ws, "GoverningOutageFacilityTable", f"A1:H{ws.max_row}")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:H{ws.max_row}"
    for row in range(2, ws.max_row + 1):
        ws.cell(row, 5).number_format = "0.0%"
        ws.cell(row, 6).number_format = "$0.0000"
        ws.cell(row, 8).alignment = Alignment(wrap_text=True, vertical="top")
    set_widths(ws, {"A": 14, "B": 24, "C": 21, "D": 24, "E": 13, "F": 15, "G": 18, "H": 62})

    ws = wb.create_sheet("Input Audit")
    ws.append(["Source sheet", "Records read", "Planning role", "Treatment"])
    roles = {
        "OrderList": "Demand population and requested service",
        "FreightRates": "Current AIR carrier, service, weight-band, and charge records",
        "WhCosts": "Facility variable cost per order unit",
        "WhCapacities": "Facility daily order-count capacity",
        "ProductsPerPlant": "Product-to-facility support relation",
        "VmiCustomers": "Customer restriction for facilities listed in this relation",
        "PlantPorts": "Facility-to-origin-port support relation",
    }
    for name, count in problem["source_counts"].items():
        treatment = "Read-only; used as current constraint" if name != "OrderList" else "Read-only; historical route fields are not locked planning choices"
        ws.append([name, count, roles[name], treatment])
    header_style(ws, 1, 1, 4)
    add_table(ws, "InputAuditTable", f"A1:D{ws.max_row}")
    set_widths(ws, {"A": 24, "B": 16, "C": 64, "D": 68})
    for row in ws.iter_rows(min_row=2, max_col=4):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    ws = wb.create_sheet("Model Notes")
    title_row(ws, "Model basis and decision limits", "These statements define how to interpret the workbook, not a substitute for order detail.", 3)
    ws.append(["Topic", "Recorded basis", "Operational implication"])
    notes = [
        (
            "Objective hierarchy",
            "First maximize valid assignments, then minimize the number of facilities with positive flow, then minimize warehouse and company freight variable cost.",
            "A smaller or cheaper plan is not comparable if it drops additional feasible orders.",
        ),
        (
            "Capacity unit",
            "Each order consumes one unit of the facility daily order-count capacity.",
            "Unit quantity drives warehouse cost but does not consume additional order-count capacity.",
        ),
        (
            "Facility/customer restriction",
            "A facility present in the customer-restriction table may serve only customers listed for that facility; facilities absent from that table remain unrestricted by it.",
            "Do not reverse the direction of the relation.",
        ),
        (
            "Freight scope",
            "Company-arranged choices use current AIR records matching origin, destination, requested service, and an inclusive weight band.",
            "The applicable company freight charge is not taken from a historical carrier field.",
        ),
        (
            "Minimum charge",
            "Company AIR freight is the greater of the row minimum charge and rate multiplied by order weight.",
            "Weight is used once; unit quantity is not multiplied into shipment weight.",
        ),
        (
            "Customer-arranged freight",
            "CRF retains zero company freight while warehouse eligibility and capacity still apply.",
            "Customer freight is outside the company variable-cost total.",
        ),
        (
            "Exception split",
            "Structural exceptions have no eligible facility path before capacity; capacity-displaced orders have at least one eligible path but are not selected within finite capacity.",
            "Neither class receives an invented assignment.",
        ),
        (
            "Facility decision boundary",
            "Facility use is inferred from positive valid current-day flow.",
            "The source does not support permanent closure, greenfield location, lease, tax, or fixed-opening economics.",
        ),
        (
            "Outage recovery",
            "Each primary-use facility is removed in turn; all other current facilities may receive recovery flow. Recoverable service is maximized before recovery variable cost is minimized.",
            "The governing outage has the lowest recoverable service; higher minimum variable cost breaks a service tie.",
        ),
    ]
    for row in notes:
        ws.append(row)
    header_style(ws, 3, 1, 3)
    set_widths(ws, {"A": 28, "B": 82, "C": 72})
    for row in ws.iter_rows(min_row=4, max_col=3):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = Border(bottom=GRID)
    ws.freeze_panes = "A4"

    for sheet in wb.worksheets:
        sheet.sheet_view.showGridLines = False
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.fitToWidth = 1
        sheet.sheet_properties.pageSetUpPr.fitToPage = True

    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    problem = load_problem(args.source)
    options, eligible_by_order = build_options(problem)
    assigned, maximum_service, reference_cost, minimum_facilities = solve_assignment(
        problem, options, minimize_facilities=True
    )
    if len(assigned) != maximum_service:
        raise RuntimeError("assignment count does not match the maximum-service objective")
    primary_facilities = sorted({option.plant for option in assigned.values()})
    outage_results = []
    for facility in primary_facilities:
        recovery, recoverable, recovery_cost, recovery_used = solve_assignment(
            problem, options, unavailable=facility
        )
        outage_results.append((facility, recovery, recoverable, recovery_cost, recovery_used))
    governing_outage = min(
        outage_results,
        key=lambda item: (item[2], -item[3], item[0]),
    )
    build_workbook(
        problem,
        options,
        eligible_by_order,
        assigned,
        outage_results,
        governing_outage,
        args.output,
    )
    print(f"wrote {args.output}")
    print(f"orders={len(problem['orders'])} assigned={maximum_service} unassigned={len(problem['orders']) - maximum_service}")
    print(f"minimum_facilities={minimum_facilities} governing_outage={governing_outage[0]} recovery={governing_outage[2]}")
    print(f"reference_variable_cost={reference_cost:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
