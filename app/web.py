from fastapi.templating import Jinja2Templates


def common_context(request):
    return {
        "csrf_token": request.session.get("csrf", ""),
        "signed_in": bool(getattr(request.state, "authenticated", False)),
    }


templates = Jinja2Templates(
    directory="app/templates", context_processors=[common_context]
)
