# Releasing BiyoVes

Releases are built by GitHub Actions and published to PyPI without a stored API
token. A successful PyPI upload is followed by a GitHub Release containing the
wheel and source distribution.

## One-time PyPI setup

Add a Trusted Publisher at
`https://pypi.org/manage/project/biyoves/settings/publishing/` with:

- Owner: `mehmetaytugyuruk`
- Repository: `biyoves-python-library`
- Workflow: `release.yml`
- Environment: `pypi`

Create a GitHub environment named `pypi`. Protection rules and a required
reviewer are recommended when the repository plan supports them.

## Release steps

1. Update the version in `pyproject.toml` and `src/biyoves/__init__.py`.
2. Move the relevant notes from `Unreleased` into a dated section in
   `CHANGELOG.md`.
3. Merge or push the changes to `main` and wait for CI to pass.
4. Create and push an annotated tag matching the package version:

   ```bash
   git tag -a v1.3.3 -m "BiyoVes v1.3.3"
   git push origin v1.3.3
   ```

The release workflow rejects mismatched tag, project, and package versions. Do
not upload the same version manually; PyPI versions are immutable.
