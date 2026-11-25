import re

from django.contrib import messages


class ManagementDraftMiddleware:
    """Acknowledge only successful saves of forms marked by the draft client."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != "POST" or not request.path.startswith("/management/") or not request.user.is_staff:
            return self.get_response(request)
        token = request.POST.get("_draft_token", "")
        if not re.fullmatch(r"[a-f0-9]{32}", token):
            return self.get_response(request)
        storage = messages.get_messages(request)
        was_used = storage.used
        existing = {id(item) for item in storage}
        storage.used = was_used
        response = self.get_response(request)
        if response.status_code in (302, 303):
            was_used = storage.used
            successful = any(item.level == messages.SUCCESS and id(item) not in existing for item in storage)
            storage.used = was_used
            if successful:
                response.set_cookie("mgmt_saved_" + token, "1", path="/management/",
                                    max_age=120, samesite="Strict", secure=request.is_secure())
        return response
