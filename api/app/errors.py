class AppError(Exception):
    def __init__(self, message, status=500, code="INTERNAL_ERROR"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def validation_error(message):
    return AppError(message, status=400, code="VALIDATION_ERROR")


def map_upstream_error(error, provider):
    code = getattr(error, "code", None)
    if code in {"ECONNABORTED", "ETIMEDOUT", "timeout"}:
        return AppError(f"{provider} request timed out.", status=504, code="UPSTREAM_TIMEOUT")
    status = getattr(error, "status_code", None)
    if status in {401, 403}:
        return AppError(
            f"{provider} rejected the configured credentials.",
            status=502,
            code="UPSTREAM_UNAUTHORIZED",
        )
    if status == 429:
        return AppError(
            f"{provider} rate limit or quota was reached. Try again later.",
            status=429,
            code="UPSTREAM_RATE_LIMIT",
        )
    if status in {500, 502, 503, 504}:
        return AppError(
            f"{provider} is busy or unavailable. Wait a moment and try a smaller area.",
            status=503,
            code="UPSTREAM_CAPACITY",
        )
    if status == 400:
        return AppError(
            f"{provider} rejected the request. Zoom in and try a smaller area.",
            status=400,
            code="UPSTREAM_REJECTED",
        )
    return AppError(f"{provider} request failed.", status=502, code="UPSTREAM_FAILURE")
