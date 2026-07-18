# Releasing

Two independent things can be released here, each triggered by pushing a
different git tag pattern. Neither requires bumping a version number
anywhere in code - the tag itself *is* the version.

## Native app (Linux/Windows/macOS binaries)

```bash
git tag v1.2.0
git push origin v1.2.0
```

Pushing a `v*` tag runs [`.github/workflows/release.yml`](.github/workflows/release.yml):
it runs the test suite, builds all three platforms, and publishes a GitHub
Release at that tag with the three binaries attached (`gh release create ...
--generate-notes`, so the release notes are auto-generated from commits
since the last tag).

`workflow_dispatch` (the "Run workflow" button in the Actions tab) runs the
same build+test on all three OSes without publishing anything - useful for
validating the pipeline without cutting a real release.

### Redoing an existing tag

If a release needs to be rebuilt from the same version number (e.g. after
rotating a baked-in credential), delete both the release and the tag, then
recreate the tag at the current commit:

```bash
gh release delete v1.2.0 --yes
git tag -d v1.2.0
git push --delete origin v1.2.0

git tag v1.2.0
git push origin v1.2.0
```

## Web/Docker image

```bash
git tag web-v1.2.0
git push origin web-v1.2.0
```

Pushing a `web-v*` tag runs [`.github/workflows/docker-publish-versioned.yml`](.github/workflows/docker-publish-versioned.yml):
it publishes `ghcr.io/kylesmart2/trakt-calendar-sync-web:1.2.0` and also
moves `:latest` to point at that same build.

This is a separate tag namespace from the native app's `v*` tags on purpose -
see [web/README.md](web/README.md)'s "Image tags" section for the full
picture: how `:latest` behaves between releases, how old commit-sha builds
get auto-pruned, and how to pin a deployment to a specific version instead
of tracking `:latest`.

`workflow_dispatch` with a `version` input re-publishes under a specific
version number without needing a new git tag (used once already, to fix a
version string that had been extracted incorrectly from the tag name).
