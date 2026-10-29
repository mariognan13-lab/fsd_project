import httpx


class RequestError(Exception):
    def __init__(self, status_code=None, code=None):
        super().__init__(code or status_code)
        self.status_code = status_code
        self.code = code


class HttpxClient:
    def __init__(self):
        self._client = httpx.Client(follow_redirects=True)

    def get(self, url, headers=None, timeout=20):
        return self._send("GET", url, headers=headers, timeout=timeout)

    def post(self, url, json=None, data=None, headers=None, timeout=20):
        return self._send("POST", url, json=json, data=data, headers=headers, timeout=timeout)

    def _send(self, method, url, json=None, data=None, headers=None, timeout=20):
        try:
            response = self._client.request(method, url, json=json, data=data, headers=headers, timeout=timeout)
        except httpx.TimeoutException as error:
            raise RequestError(code="ETIMEDOUT") from error
        except httpx.HTTPError as error:
            raise RequestError(code="UPSTREAM_FAILURE") from error
        if response.status_code >= 400:
            raise RequestError(status_code=response.status_code)
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            return response.json()
        text = response.text
        if text.lstrip().startswith("{") or text.lstrip().startswith("["):
            return response.json()
        return text
