# 🚀 Quick Release Guide

## TL;DR - Create a Release in 3 Steps

```bash
# 1. Bump version (patch/minor/major)
./scripts/bump-version.sh patch

# 2. Push when prompted (or push manually)
git push origin main

# 3. Watch GitHub Actions create your release!
# Visit: https://github.com/YOUR_USERNAME/caipng/actions
```

## Version Bump Cheat Sheet

| Command | Current | New | Use Case |
|---------|---------|-----|----------|
| `./scripts/bump-version.sh patch` | 1.0.0 | 1.0.1 | Bug fixes |
| `./scripts/bump-version.sh minor` | 1.0.1 | 1.1.0 | New features |
| `./scripts/bump-version.sh major` | 1.1.0 | 2.0.0 | Breaking changes |

## What Happens Automatically

```
1. You bump version and push
   ↓
2. GitHub Actions detects version change
   ↓
3. Runs all tests (backend, frontend, training)
   ↓
4. Builds production artifacts
   ↓
5. Creates GitHub release with:
   - Auto-generated changelog
   - Source code archives (.tar.gz, .zip)
   - Frontend build
   - Release notes
   ↓
6. Release is published! 🎉
```

## Files Changed by Version Bump

```
backend/package.json   → version: "1.0.1"
frontend/package.json  → version: "1.0.1"
```

## Release Contents

Each release includes:

📦 **Source Archives**
- `caipng-v1.0.1-source.tar.gz`
- `caipng-v1.0.1-source.zip`

🏗️ **Build Artifacts**
- `caipng-v1.0.1-frontend-build.tar.gz`

📝 **Release Notes**
- Version numbers
- Commit history since last release
- Installation instructions
- Documentation links

## Script Options

```bash
# Bump with custom commit message
./scripts/bump-version.sh minor -m "feat: add awesome feature"

# Bump without committing (manual control)
./scripts/bump-version.sh patch --no-commit

# View help
./scripts/bump-version.sh --help
```

## Workflow Triggers

✅ **Creates Release:**
- Push to main branch
- Version changed in package.json

❌ **Skips Release:**
- Version unchanged
- Only docs/markdown updated
- PR (not merged to main)

## Monitoring

### Check Workflow Status
```bash
# Visit GitHub Actions
https://github.com/YOUR_USERNAME/caipng/actions

# Or use gh CLI
gh run list --workflow=release.yml
```

### View Latest Release
```bash
# Visit Releases
https://github.com/YOUR_USERNAME/caipng/releases/latest

# Or use gh CLI
gh release view --web
```

## Troubleshooting

**❓ "No release created"**
```bash
# Check if version actually changed
git diff HEAD~1 backend/package.json frontend/package.json

# Check workflow logs
gh run view --log
```

**❓ "Build failed"**
```bash
# Test build locally first
cd backend && npm run build
cd frontend && npm run build

# Fix issues, then push again
```

**❓ "Tests failed"**
```bash
# Run tests locally
cd backend && npm test
cd frontend && npm test

# Fix failing tests, then retry
```

## Pro Tips

💡 **Always test locally before bumping version**
```bash
npm run build  # Both backend and frontend
npm test       # Run all tests
```

💡 **Use conventional commits for better changelogs**
```bash
git commit -m "feat: add new feature"     # Feature
git commit -m "fix: resolve bug"          # Bug fix
git commit -m "docs: update readme"       # Documentation
git commit -m "chore: update deps"        # Maintenance
```

💡 **Check Actions tab if release fails**
- Green ✅ = Success
- Red ❌ = Failed (click for logs)
- Yellow 🟡 = In progress

## Common Workflows

### 🐛 Bug Fix
```bash
# 1. Fix the bug
git add .
git commit -m "fix: resolve camera initialization bug"
git push

# 2. Bump patch version
./scripts/bump-version.sh patch
# → v1.0.0 becomes v1.0.1
```

### ✨ New Feature
```bash
# 1. Add the feature
git add .
git commit -m "feat: add dark mode support"
git push

# 2. Bump minor version
./scripts/bump-version.sh minor
# → v1.0.1 becomes v1.1.0
```

### 💥 Breaking Change
```bash
# 1. Make breaking changes
git add .
git commit -m "feat!: migrate to API v2

BREAKING CHANGE: All endpoints now use /api/v2/"
git push

# 2. Bump major version
./scripts/bump-version.sh major
# → v1.1.0 becomes v2.0.0
```

## Quick Commands Reference

```bash
# Version bump
./scripts/bump-version.sh [major|minor|patch]

# Check current version
node -p "require('./backend/package.json').version"

# View git tags
git tag -l

# List releases (gh CLI)
gh release list

# Create release manually (if needed)
gh release create v1.0.0 --generate-notes

# Delete tag and release
git tag -d v1.0.0
git push --delete origin v1.0.0
gh release delete v1.0.0
```

## Need Help?

📖 Full documentation: `docs/RELEASE_WORKFLOW.md`

🔧 Workflow file: `.github/workflows/release.yml`

🐛 Issues: https://github.com/YOUR_USERNAME/caipng/issues

---

**Happy Releasing! 🚀**
