import csv
import io
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models import PlanningState, ScheduleVersion
from app.services.planning import (
    lock_state,
    saved_month,
    schedule_view,
    serialize,
    replace_month,
)
from app.services.schedule_generator import generate_monthly_schedule
from app.web import templates

router = APIRouter()


def calendar_redirect(year, month, **query):
    extra = "".join(f"&{key}={value}" for key, value in query.items())
    return RedirectResponse(
        f"/calendario?year={year}&month={month}{extra}", status_code=303
    )


def require_version(db, version_id):
    version = db.get(ScheduleVersion, version_id)
    if not version:
        raise HTTPException(404, "Versión no encontrada.")
    return version


@router.get("/calendario")
def calendar_page(
    request: Request,
    year: int | None = Query(None, ge=1, le=9999),
    month: int | None = Query(None, ge=1, le=12),
    version: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    today = date.today()
    year, month = year or today.year, month or today.month
    preview = require_version(db, version) if version else None
    if preview:
        year, month = preview.year, preview.month
    state = db.get(PlanningState, 1)
    history = (
        db.query(ScheduleVersion)
        .filter_by(year=year, month=month)
        .order_by(ScheduleVersion.id.desc())
        .all()
    )
    context = schedule_view(db, year, month, preview.assignments if preview else None)
    context.update(
        preview=preview,
        revision=state.revision,
        history=history,
        stale=bool(
            preview
            and preview.kind == "draft"
            and preview.base_revision != state.revision
        ),
        saved=request.query_params.get("saved") == "true",
    )
    return templates.TemplateResponse(
        request=request, name="calendario.html", context=context
    )


@router.post("/calendario/generar")
def generate_calendar(
    year: int = Form(..., ge=1, le=9999),
    month: int = Form(..., ge=1, le=12),
    revision: int = Form(...),
    db: Session = Depends(get_db),
):
    state = lock_state(db, revision)
    version = ScheduleVersion(
        year=year,
        month=month,
        kind="draft",
        label="Borrador generado",
        assignments=generate_monthly_schedule(db, year, month),
        base_revision=state.revision,
    )
    db.add(version)
    db.commit()
    return calendar_redirect(year, month, version=version.id)


@router.post("/calendario/versiones/{version_id}/aplicar")
def apply_version(
    version_id: int, revision: int = Form(...), db: Session = Depends(get_db)
):
    state = lock_state(db, revision)
    version = require_version(db, version_id)
    if version.kind == "draft" and version.base_revision != state.revision:
        raise HTTPException(409, "Los datos cambiaron. Generá un nuevo borrador.")
    if version.kind == "draft":
        for row in serialize(saved_month(db, version.year, version.month)):
            if row["locked"] and row not in version.assignments:
                raise HTTPException(
                    409, "El borrador no conserva las asignaciones bloqueadas."
                )
    replace_month(
        db,
        version.year,
        version.month,
        version.assignments,
        state,
        "Antes de aplicar una versión",
    )
    return calendar_redirect(version.year, version.month, saved="true")


@router.post("/calendario/editar")
def edit_assignment(
    day: date = Form(...),
    slot: int = Form(..., ge=1, le=4),
    person_id: str = Form(""),
    locked: bool = Form(False),
    revision: int = Form(...),
    db: Session = Depends(get_db),
):
    state = lock_state(db, revision)
    rows = [
        row
        for row in serialize(saved_month(db, day.year, day.month))
        if not (row["date"] == day.isoformat() and row["slot"] == slot)
    ]
    if person_id:
        try:
            pid = int(person_id)
        except ValueError as exc:
            raise HTTPException(400, "Persona inválida.") from exc
        rows.append(
            dict(
                person_id=pid,
                date=day.isoformat(),
                slot=slot,
                role="substitute" if slot == 4 else "primary",
                locked=locked,
            )
        )
    elif locked:
        raise HTTPException(400, "Elegí una persona antes de bloquear una asignación.")
    replace_month(
        db,
        day.year,
        day.month,
        rows,
        state,
        "Antes de editar una asignación",
        allow_existing_conflicts=True,
    )
    return calendar_redirect(day.year, day.month, saved="true")


@router.post("/calendario/intercambiar")
def swap_assignments(
    year: int = Form(..., ge=1, le=9999),
    month: int = Form(..., ge=1, le=12),
    first: str = Form(...),
    second: str = Form(...),
    revision: int = Form(...),
    db: Session = Depends(get_db),
):
    state = lock_state(db, revision)
    rows = serialize(saved_month(db, year, month))
    by_key = {f"{r['date']}:{r['slot']}": r for r in rows}
    a, b = by_key.get(first), by_key.get(second)
    if not a or not b or first == second:
        raise HTTPException(400, "Elegí dos asignaciones diferentes.")
    if a["locked"] or b["locked"]:
        raise HTTPException(
            409, "Desbloqueá las asignaciones antes de intercambiarlas."
        )
    a["person_id"], b["person_id"] = b["person_id"], a["person_id"]
    replace_month(
        db,
        year,
        month,
        rows,
        state,
        "Antes de intercambiar asignaciones",
        allow_existing_conflicts=True,
    )
    return calendar_redirect(year, month, saved="true")


def safe_csv(value):
    text = str(value)
    return (
        "'" + text
        if text.lstrip().startswith(("=", "+", "-", "@"))
        or text.startswith(("\t", "\r", "\n"))
        else text
    )


def ics_escape(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r", "")
    )


def fold_ics(line):
    lines, part = [], ""
    for char in line:
        if len((part + char).encode("utf-8")) > 75:
            lines.append(part)
            part = " "
        part += char
    lines.append(part)
    return "\r\n".join(lines)


@router.get("/calendario/exportar/{format}")
def export_calendar(
    format: str,
    year: int = Query(..., ge=1, le=9999),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    context = schedule_view(db, year, month)
    if format == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(["Fecha", "Lugar", "Rol", "Persona", "Bloqueada", "Estado"])
        for day in context["schedule"]:
            for e in day["entries"]:
                writer.writerow(
                    [
                        day["day"].isoformat(),
                        e["slot"],
                        "Suplente" if e["slot"] == 4 else "Guardia",
                        (
                            safe_csv(e["person"].full_name)
                            if e["person"]
                            else "Sin asignar"
                        ),
                        "Sí" if e["row"] and e["row"]["locked"] else "No",
                        (
                            "Revisar"
                            if e["conflict"]
                            else "Completa" if e["row"] else "Pendiente"
                        ),
                    ]
                )
        data = "\ufeff" + buffer.getvalue()
        media = "text/csv"
    elif format == "ics":
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Gestion Guardias//ES",
            "CALSCALE:GREGORIAN",
        ]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        for day in context["schedule"]:
            for e in day["entries"]:
                if not e["person"]:
                    continue
                role = "Suplente" if e["slot"] == 4 else "Guardia"
                lines += [
                    "BEGIN:VEVENT",
                    f"UID:guardias-{day['day'].isoformat()}-{e['slot']}@gestion-guardias",
                    f"DTSTAMP:{stamp}",
                    f"DTSTART;VALUE=DATE:{day['day'].strftime('%Y%m%d')}",
                    "DURATION:P1D",
                    f"SUMMARY:{ics_escape(role+': '+e['person'].full_name)}",
                    f"DESCRIPTION:{ics_escape('Requiere revisión' if e['conflict'] else 'Asignación guardada')}",
                    "END:VEVENT",
                ]
        lines.append("END:VCALENDAR")
        data = "\r\n".join(fold_ics(line) for line in lines) + "\r\n"
        media = "text/calendar"
    else:
        raise HTTPException(404, "Formato no disponible.")
    return Response(
        data,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="guardias-{year:04d}-{month:02d}.{format}"'
        },
    )
