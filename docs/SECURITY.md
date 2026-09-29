# Security

Sensitive safety endpoints require authentication and role checks. The digital card API requires login and excludes national ID, medical data, and emergency PIN. CSRF exemptions were removed from safety endpoints. Production settings require an environment secret and explicit hosts. Remaining work includes rate limiting and a complete export authorization review.
