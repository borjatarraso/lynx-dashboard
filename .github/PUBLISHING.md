# Publishing to PyPI

This package is published to PyPI via **trusted publishing**
(OIDC, no API tokens).

## First-time setup (operator, once per package)

1. Log in at https://pypi.org and navigate to "Your projects" → "Publishing".
2. Add a new pending publisher:
   - **PyPI project name**: lynx-dashboard
   - **Owner**: `borjatarraso`
   - **Repository**: `lynx-dashboard`
   - **Workflow filename**: `publish.yml`
   - **Environment**: `pypi`
3. In the GitHub repo, create a protected environment named `pypi`
   (Settings → Environments → New environment).

## Shipping a release

```bash
# Bump version in pyproject.toml + __init__.py, update CHANGELOG, commit,
# then:
git tag -a v5.2 -m "lynx-dashboard v5.2"
git push origin v5.2
```

The workflow picks it up and publishes automatically.
