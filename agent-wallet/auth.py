"""Token acquisition that survives the DevNet 900-second expiry.

Measured on 29 Aug 2026: the Cantor8 DevNet Keycloak token has
`expires_in: 900`. The toolkit's c8lab.py caches its token in a dict and never
refreshes it, so any long-running process -- an indexer, an MCP server, a load
test -- starts working and then returns 401 fifteen minutes later. It reads
like a streaming bug and it is an auth bug.

This module refreshes before expiry instead. `now_fn` is injectable so the
expiry logic is testable without waiting fifteen minutes or touching DevNet.
"""
import json, threading, time, urllib.parse, urllib.request

# Refresh this many seconds BEFORE the token actually expires, so a request
# in flight cannot straddle the boundary.
SKEW = 60


class TokenSource:
    def __init__(self, idp, client_id, client_secret, realm="master",
                 now_fn=time.time, fetch_fn=None):
        self.idp, self.cid, self.csec, self.realm = idp, client_id, client_secret, realm
        self._now = now_fn
        self._fetch = fetch_fn or self._http_fetch
        self._token = None
        self._expires_at = 0.0
        self.refreshes = 0
        # Load tests call token() from several submission threads. Without a
        # lock they can all observe an expired token and stampede the IDP.
        self._lock = threading.Lock()

    def _http_fetch(self):
        data = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self.cid, "client_secret": self.csec}).encode()
        url = f"{self.idp}/realms/{self.realm}/protocol/openid-connect/token"
        r = json.loads(urllib.request.urlopen(
            urllib.request.Request(url, data=data), timeout=30).read())
        return r["access_token"], float(r.get("expires_in", 900))

    def token(self):
        """Current token, refreshed if it is within SKEW of expiring."""
        with self._lock:
            if self._token is None or self._now() >= self._expires_at - SKEW:
                self._token, ttl = self._fetch()
                self._expires_at = self._now() + ttl
                self.refreshes += 1
            return self._token

    def invalidate(self):
        """Force a refresh. Call this on a 401 -- the server is the authority
        on whether a token is dead, not our arithmetic."""
        with self._lock:
            self._token = None
