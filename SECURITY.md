# Security Policy — biz-prospector

## API Key Handling
- All API keys stored in `config/settings.yaml` (gitignored)
- Never commit API keys to version control
- Example config provided in `config/settings.example.yaml` with placeholder values

## Data Privacy
- Scraped business data (names, addresses, phones, emails) stored locally in `data/` directory
- No data is transmitted except to configured API services
- Contact emails are verified before outreach delivery

## Reporting Vulnerabilities
Report security issues to the project owner directly.

## Security Scanning
- **SAST:** Semgrep (OWASP Top Ten + security-audit rulesets) runs in CI
- **Secret detection:** gitleaks runs in pre-commit hook and CI
- **Dependency audit:** pip-audit runs in CI
- **License compliance:** pip-licenses checks for copyleft licenses in CI
