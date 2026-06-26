# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |

## Reporting a Vulnerability

Please report security vulnerabilities via GitHub Issues or by emailing the maintainer. Do not open a public issue for security concerns.

## Security Practices

- No hardcoded secrets or API keys
- All data stored locally in SQLite
- Input validation on all CLI arguments (token counts, provider names)
- Parameterized SQL queries to prevent injection
- Pydantic models for type validation
- Dependencies pinned by version
