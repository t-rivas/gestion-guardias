import random
from collections import Counter, defaultdict, deque
from datetime import date
from random import Random
from sqlalchemy.orm import Session
from app.models import Availability, GuardAssignment, Person
from app.services.availability_rules import (
    ROLES,
    is_person_available,
    load_role_availability,
)
from app.services.planning import month_days, week_bounds, validate_schedule, shift_day

ASSIGNMENT_SLOTS = (("primary", 1), ("primary", 2), ("primary", 3), ("substitute", 4))
MAX_WEEKLY_ASSIGNMENTS = 2


class Flow:
    """Successive shortest augmenting paths; reverse edges revise earlier choices."""

    def __init__(self, count):
        self.graph = [[] for _ in range(count)]

    def add(self, source, target, capacity, cost=0):
        edge = [target, len(self.graph[target]), capacity, cost]
        self.graph[source].append(edge)
        self.graph[target].append([source, len(self.graph[source]) - 1, 0, -cost])
        return edge

    def solve(self, source, sink):
        while True:
            distance = [float("inf")] * len(self.graph)
            distance[source] = 0
            parents = [None] * len(self.graph)
            queue, queued = deque([source]), {source}
            while queue:
                node = queue.popleft()
                queued.remove(node)
                for idx, edge in enumerate(self.graph[node]):
                    target, _, capacity, cost = edge
                    if capacity and distance[target] > distance[node] + cost:
                        distance[target] = distance[node] + cost
                        parents[target] = (node, idx)
                        if target not in queued:
                            queue.append(target)
                            queued.add(target)
            if parents[sink] is None:
                return
            node = sink
            while node != source:
                previous, idx = parents[node]
                edge = self.graph[previous][idx]
                edge[2] -= 1
                self.graph[node][edge[1]][2] += 1
                node = previous


def improve_rest(selected, eligible_edges, fixed):
    """Swap equal-capacity choices to reduce consecutive days without losing coverage."""
    days = list(selected)

    def score():
        members = {day: ids | selected.get(day, set()) for day, ids in fixed.items()}
        for day, ids in selected.items():
            members.setdefault(day, set()).update(ids)
        return sum(
            len(ids & members.get(shift_day(day, -1), set()))
            for day, ids in members.items()
            if day != date.min
        )

    current = score()
    while True:
        improved = False
        for index, first_day in enumerate(days):
            for second_day in days[index + 1 :]:
                for first_person in sorted(selected[first_day]):
                    for second_person in sorted(selected[second_day]):
                        if (
                            first_person == second_person
                            or second_person in selected[first_day]
                            or first_person in selected[second_day]
                        ):
                            continue
                        if (first_day, second_person) not in eligible_edges or (
                            second_day,
                            first_person,
                        ) not in eligible_edges:
                            continue
                        selected[first_day].remove(first_person)
                        selected[first_day].add(second_person)
                        selected[second_day].remove(second_person)
                        selected[second_day].add(first_person)
                        candidate = score()
                        if candidate < current:
                            current = candidate
                            improved = True
                            break
                        selected[first_day].remove(second_person)
                        selected[first_day].add(first_person)
                        selected[second_day].remove(first_person)
                        selected[second_day].add(second_person)
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break
        if not improved:
            return selected


def generate_monthly_schedule(
    db: Session, year: int, month: int, rng: Random | None = None
) -> list[dict]:
    """Return a maximum-coverage draft without changing saved assignments.

    ISO weeks are independent capacity problems. Include adjacent months and locks;
    min-cost max-flow finds all feasible coverage before preferring balanced workloads.
    """
    rng = rng or random.SystemRandom()
    days = month_days(year, month)
    start, end = week_bounds(days)
    people = db.query(Person).filter(Person.active.is_(True)).order_by(Person.id).all()
    blocked = {p.id: p.blocked_days for p in people}
    role_availability = load_role_availability(db, days[0], days[-1])
    existing = (
        db.query(GuardAssignment).filter(GuardAssignment.date.between(start, end)).all()
    )
    adjacent = [a for a in existing if a.date < days[0] or a.date > days[-1]]
    locked = [a for a in existing if a.date in days and a.locked]
    rows = [
        dict(
            person_id=a.person_id,
            date=a.date.isoformat(),
            slot=a.slot,
            role=a.role,
            locked=True,
        )
        for a in locked
    ]
    validate_schedule(db, year, month, rows)
    weekly = Counter((a.date.isocalendar()[:2], a.person_id) for a in adjacent + locked)
    monthly = Counter(a.person_id for a in locked)
    role_counts = {
        role: Counter(a.person_id for a in locked if a.role == role) for role in ROLES
    }
    groups = defaultdict(list)
    for day in days:
        groups[day.isocalendar()[:2]].append(day)
    for week, week_days in groups.items():
        # source -> day/role -> day/person -> person -> sink.
        # Shared day/person capacity prevents taking both roles on the same date.
        day_role_nodes = {
            (day, role): 1 + i * 2 + j
            for i, day in enumerate(week_days)
            for j, role in enumerate(ROLES)
        }
        person_day_start = 1 + len(week_days) * 2
        person_day_nodes = {
            (day, p.id): person_day_start + i * len(people) + j
            for i, day in enumerate(week_days)
            for j, p in enumerate(people)
        }
        person_start = person_day_start + len(week_days) * len(people)
        person_nodes = {p.id: person_start + i for i, p in enumerate(people)}
        sink = person_start + len(people)
        flow = Flow(sink + 1)
        edges = {}
        for day in week_days:
            day_locks = [a for a in locked if a.date == day]
            locked_ids = {a.person_id for a in day_locks}
            for role in ROLES:
                capacity = (3 if role == "primary" else 1) - sum(
                    a.role == role for a in day_locks
                )
                flow.add(0, day_role_nodes[(day, role)], capacity)
                candidates = list(people)
                rng.shuffle(candidates)
                for p in candidates:
                    if p.id in locked_ids or not is_person_available(
                        p.id, day, *role_availability[role], blocked
                    ):
                        continue
                    neighbors = {shift_day(day, -1), shift_day(day, 1)} - {day}
                    rest_cost = 3 * sum(
                        a.person_id == p.id and a.date in neighbors
                        for a in adjacent + locked
                    )
                    # Fill primary guards first when equally large partial schedules are possible.
                    # Max-flow always maximizes total coverage before comparing these costs.
                    role_cost = role_counts[role][p.id] + (
                        10_000 if role == "substitute" else 0
                    )
                    edges[(day, role, p.id)] = flow.add(
                        day_role_nodes[(day, role)],
                        person_day_nodes[(day, p.id)],
                        1,
                        rest_cost + role_cost,
                    )
            for p in people:
                flow.add(person_day_nodes[(day, p.id)], person_nodes[p.id], 1)
        for p in people:
            for extra in range(max(0, 2 - weekly[(week, p.id)])):
                flow.add(person_nodes[p.id], sink, 1, (monthly[p.id] + extra) * 10)
        flow.solve(0, sink)
        selected = {
            role: {
                day: {
                    p.id
                    for p in people
                    if (day, role, p.id) in edges and edges[(day, role, p.id)][2] == 0
                }
                for day in week_days
            }
            for role in ROLES
        }
        fixed = defaultdict(set)
        for a in adjacent + locked:
            fixed[a.date].add(a.person_id)
        for row in rows:
            fixed[date.fromisoformat(row["date"])].add(row["person_id"])
        # Rest improvements keep each person's role counts and weekly capacity unchanged.
        for role in ROLES:
            other_role = "substitute" if role == "primary" else "primary"
            role_fixed = {day: set(ids) for day, ids in fixed.items()}
            for day, ids in selected[other_role].items():
                role_fixed.setdefault(day, set()).update(ids)
            eligible = {
                (day, pid): edge
                for (day, edge_role, pid), edge in edges.items()
                if edge_role == role and pid not in selected[other_role][day]
            }
            improve_rest(selected[role], eligible, role_fixed)
        for day in week_days:
            for role in ROLES:
                selected_ids = sorted(selected[role][day])
                rng.shuffle(selected_ids)
                free_slots = [
                    slot
                    for slot_role, slot in ASSIGNMENT_SLOTS
                    if slot_role == role
                    and not any(a.date == day and a.slot == slot for a in locked)
                ]
                for slot, pid in zip(free_slots, selected_ids):
                    rows.append(
                        dict(
                            person_id=pid,
                            date=day.isoformat(),
                            slot=slot,
                            role=role,
                            locked=False,
                        )
                    )
                    monthly[pid] += 1
                    role_counts[role][pid] += 1
    rows.sort(key=lambda r: (r["date"], r["slot"]))
    validate_schedule(db, year, month, rows)
    return rows
