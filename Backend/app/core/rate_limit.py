"""
Shared rate limiter (slowapi, backed by an in-memory store by default).

Applied selectively — not globally — to the endpoints where abuse is most
consequential: auth (credential stuffing / signup spam) and checkout
(Razorpay order creation, which costs real API calls against the payment
provider). Read-heavy endpoints like product search aren't rate-limited
here, since aggressive limits there would hurt legitimate shoppers more
than they'd stop abuse.

In-memory storage means limits are per-process — correct for a single
backend instance. If the API scales horizontally, swap the default storage
for Redis (slowapi supports this via `storage_uri="redis://..."` on the
Limiter constructor) so limits are enforced consistently across instances;
noted here rather than silently left as a scaling gap.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
