# Security policy

## Supported versions

Only the latest release on `main` receives fixes.

## Reporting a vulnerability

Report privately through
[GitHub Security Advisories](https://github.com/oddurs/fairest-coin/security/advisories/new).
Do not open a public issue.

You will get an acknowledgement within 7 days and a decision within 30. Credit is given
in the advisory unless you ask otherwise.

The most likely class of issue in this project is a leaked IBM Quantum API key. The key
is read from the environment and must never be committed; if you find one in the
history, report it here.
