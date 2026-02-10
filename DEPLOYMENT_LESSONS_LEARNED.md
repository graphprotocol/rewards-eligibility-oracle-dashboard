# Deployment Lessons Learned

This document captures important lessons learned during the v0.1.0 multi-environment deployment that were not properly documented beforehand.

## Docker Image Caching Issue

### Problem
When deploying to production, the standard deployment commands did not pull the new image:

```bash
# This did NOT work as expected:
docker compose pull reo reo-scheduler
docker compose up -d reo reo-scheduler
```

The containers continued running the old image (v0.0.19) instead of the newly built v0.1.0.

### Root Cause
Docker's layer caching and the `:latest` tag behavior caused the issue:
- `docker compose pull` saw that `ghcr.io/graphprotocol/rewards-eligibility-oracle-dashboard:latest` already existed locally
- It didn't actually pull the newer image from GHCR
- Containers were recreated but used the cached old image

### Solution
Force pull the image before recreating containers:

```bash
# Force pull the latest image (ignores local cache)
docker pull ghcr.io/graphprotocol/rewards-eligibility-oracle-dashboard:latest

# Verify the image was updated
docker images ghcr.io/graphprotocol/rewards-eligibility-oracle-dashboard --format "{{.ID}} {{.CreatedAt}}"

# Force recreate containers with the new image
docker compose up -d --force-recreate reo reo-scheduler
```

### Key Takeaway
**Always force pull images** when deploying to ensure you get the latest version, even if the tag is `:latest`.

## GitHub Actions Tag Behavior

### Problem
PR builds created Docker images with invalid tags, causing build failures:
```
ERROR: invalid tag "ghcr.io/graphprotocol/rewards-eligibility-oracle-dashboard:-d7eaa7f"
```

### Root Cause
The workflow configuration used `type=sha,prefix={{branch}}-` which created invalid tags for PRs:
- For PRs, `{{branch}}` evaluates to empty or malformed values
- Result: `:-d7eaa7f` instead of valid tag like `pr-1-d7eaa7f`

### Solution
Changed the tag configuration to avoid branch prefix:
```yaml
# Before (broken):
type=sha,prefix={{branch}}-

# After (fixed):
type=sha,prefix=
```

### GitHub Actions Tag Behavior (Documented)

| Event | Tags Created | Notes |
|-------|--------------|-------|
| Push to `main` | `:latest`, `:<sha>` | Updates production image |
| PR created | `:pr-<number>`, `:<sha>` | For testing PRs only |
| Tag push `v*.*.*` | `:latest`, `:<version>`, `:<major>.<minor>` | Release builds |

### Key Takeaway
**PR builds don't update the `:latest` tag.** Only pushes to `main` create production images. After merging a PR, wait for the `main` branch workflow to complete before deploying.

## Deployment Workflow (Corrected)

### Actual Working Deployment Process

```bash
# 1. Merge PR to main (triggers GitHub Actions)
gh pr merge <pr-number> --squash

# 2. Wait for main branch workflow to complete
# Monitor: https://github.com/graphprotocol/rewards-eligibility-oracle-dashboard/actions
# Wait for "Build and Push Docker Image" workflow on main branch to succeed

# 3. Navigate to infrastructure
cd /home/pdiogo/hosted-apps/repos/dashboard-infrastructure

# 4. Force pull the new image (critical step!)
docker pull ghcr.io/graphprotocol/rewards-eligibility-oracle-dashboard:latest

# 5. Verify image timestamp is recent
docker images ghcr.io/graphprotocol/rewards-eligibility-oracle-dashboard --format "{{.ID}} {{.CreatedAt}}"

# 6. Force recreate containers
docker compose up -d --force-recreate reo reo-scheduler

# 7. Verify new version is running
docker exec reo-scheduler-prod python -c "import generate_dashboard; print(generate_dashboard.VERSION)"

# 8. Check logs
docker logs reo-scheduler-prod --tail 20

# 9. Verify production URL
curl -s https://hub.thegraph.foundation/reo/ | grep -o "environmentData"
```

### Critical Steps Previously Missing

1. **Wait for main branch workflow** - PR workflows don't create production images
2. **Force pull the image** - Docker caches `:latest` tag
3. **Verify image timestamp** - Confirm you actually got the new image
4. **Use `--force-recreate`** - Ensures containers use the new image
5. **Verify version in container** - Don't assume, check explicitly

## Production Testing Gaps

### What We Verified (Insufficient)
- ✅ Checked version number in container
- ✅ Verified HTML contains `environmentData`
- ✅ Verified CSS classes present (`env-badge`, `environment-select`)
- ✅ Verified text "Arbitrum Sepolia" appears in HTML

### What We Should Have Verified (Missing)
- ❌ **Click the environment toggle** - Verify it actually switches environments
- ❌ **Verify localStorage persistence** - Refresh page and confirm selection persists
- ❌ **Check both environments have data** - Verify mainnet and testnet both populate
- ❌ **Test contract info display** - Verify address, block, and timestamp display correctly
- ❌ **Verify visual indicator updates** - Confirm badge color changes between environments
- ❌ **Test in actual browser** - Use browser dev tools to verify JavaScript works
- ❌ **Check for console errors** - Verify no JavaScript errors on page load or toggle

### Production Testing Checklist (For Next Time)

```bash
# 1. Generate screenshot before changes
curl -s https://hub.thegraph.foundation/reo/ > /tmp/before.html

# 2. Deploy changes
# [deployment steps]

# 3. Verify page loads without errors
curl -s -o /dev/null -w "%{http_code}" https://hub.thegraph.foundation/reo/

# 4. Use headless browser to test functionality
# (This requires agent-browser or similar tool)
agent-browser open "https://hub.thegraph.foundation/reo/"
agent-browser screenshot /tmp/reo-dashboard.png
agent-browser snapshot | grep "environment-select"  # Verify toggle exists

# 5. Manual browser testing (recommended for UI changes)
# - Open URL in browser
# - Open DevTools Console
# - Check for JavaScript errors
# - Click environment toggle
# - Verify data switches
# - Refresh page
# - Verify selection persisted in localStorage

# 6. Verify multiple environments
# Check that both mainnet and testnet options exist and work

# 7. Regression test
# Verify existing functionality still works (search, sort, eligibility badges)
```

## Timing Issues

### GitHub Actions Workflow Timing

After merging a PR to `main`:
1. GitHub Actions triggers automatically
2. Build takes ~30-40 seconds
3. Image is pushed to GHCR
4. **Only then** is the image available for deployment

### Deployment Timing

```bash
# After merge, check workflow status:
gh run list --branch main --limit 1

# Wait for status to show "completed success"
# The "Completed At" timestamp shows when image is ready

# Only then proceed with deployment
```

### Lesson
**Don't deploy immediately after merging.** Wait for the GitHub Actions workflow to complete first.

## Container Recreation Behavior

### Problem Discovered
`docker compose up -d` doesn't always recreate containers with new images.

### Docker Compose Behavior
- `docker compose up -d` - Only recreates if config changed
- `docker compose up -d --force-recreate` - Always recreates containers
- Without `--force-recreate`, containers may keep using old image even if `docker compose pull` was run

### Solution
Always use `--force-recreate` when deploying updates:
```bash
docker compose up -d --force-recreate <service>
```

## Version Verification in Production

### Problem
After deployment, we discovered the container was still running v0.0.19.

### How to Verify Version
```bash
# Method 1: Check Python module (most reliable)
docker exec <container> python -c "import generate_dashboard; print(generate_dashboard.VERSION)"

# Method 2: Check image digest
docker inspect <container> | grep "Image"

# Method 3: Check image creation time
docker images ghcr.io/graphprotocol/<image>:latest --format "{{.CreatedAt}}"

# Method 4: Check HTML for version-specific features
docker exec <container> cat /app/output/index.html | grep "<feature>"
```

### Lesson
**Never assume deployment succeeded.** Always verify the specific version is running.

## Documentation Updates Needed

### Files to Update

1. **DEPLOYMENT.md** - Add corrected deployment workflow
2. **CLAUDE.md** - Add Docker caching warning
3. **TESTING.md** (create) - Production testing checklist
4. **.github/workflows/docker.yml** - Already fixed tag issue

### Key Sections to Add

- Force pull requirement
- GitHub Actions timing considerations
- Production testing checklist
- Version verification steps
- Browser-based testing requirements

## Summary

### Critical Deployment Issues

1. **Docker image caching** - Must force pull latest images
2. **GitHub Actions timing** - PR builds ≠ production builds
3. **Container recreation** - Must use `--force-recreate`
4. **Testing gaps** - Need actual browser testing for UI changes

### Deployment Command Sequence (Memorize)

```bash
# After merge, wait for workflow...
gh run list --branch main --limit 1  # Wait for "completed success"

# Force pull new image
docker pull ghcr.io/graphprotocol/<image>:latest

# Force recreate containers
docker compose up -d --force-recreate <services>

# Verify version
docker exec <container> python -c "import <module>; print(<module>.VERSION)"

# Test in browser
# [Open URL in actual browser and verify functionality]
```

### Production Testing Checklist (Before Calling "Done")

- [ ] Page loads without errors (HTTP 200)
- [ ] Version number is correct
- [ ] No JavaScript console errors
- [ ] New features work in browser
- [ ] Old features still work (regression test)
- [ ] Visual changes match expectations
- [ ] Toggle/interactive elements function correctly
- [ ] localStorage persistence works
- [ ] Multiple environments/data sources work

---

## Creating Releases

### Version Tagging and Release Workflow

The repository includes an automated GitHub release workflow (`.github/workflows/release.yml`) that creates GitHub releases when version tags are pushed.

#### How to Create a Release

1. **Update version in `generate_dashboard.py`:**
   ```python
   VERSION = "0.1.1"  # Increment as needed
   ```

2. **Commit and push changes:**
   ```bash
   git add .
   git commit -m "Bump version to 0.1.1: Fix block number parsing and UI issues"
   git push origin main
   ```

3. **Wait for GitHub Actions workflow to complete** (builds and pushes Docker image)

4. **Create and push version tag:**
   ```bash
   git tag -a v0.1.1 -m "Release v0.1.1: Fix block number parsing and UI issues"
   git push origin v0.1.1
   ```

5. **GitHub Actions will automatically:**
   - Generate changelog from commits since last tag
   - Create GitHub Release with changelog
   - Docker image is already built from step 3

#### Version Increment Rules (Semantic Versioning)

- **PATCH** (0.0.X): Bug fixes, small improvements, documentation updates
  - Example: `v0.1.0` → `v0.1.1` (Fix deployment timestamp display)
- **MINOR** (0.X.0): New features, backward-compatible changes
  - Example: `v0.1.0` → `v0.2.0` (Add mainnet environment support)
- **MAJOR** (X.0.0): Breaking changes, incompatible API changes
  - Example: `v0.1.0` → `v1.0.0` (Stable production release)

#### Release Workflow Details

The release workflow (`release.yml`) runs when tags matching `v*.*.*` are pushed:

1. **Checkout code** with full history
2. **Extract version** from tag reference
3. **Generate changelog** from commits since last tag
4. **Create GitHub Release** with:
   - Release name: `Release v0.1.1`
   - Tag: `v0.1.1`
   - Changelog: Auto-generated from commit messages

#### After Creating a Release

1. **Verify GitHub Release** was created: https://github.com/graphprotocol/rewards-eligibility-oracle-dashboard/releases

2. **Deploy to production** following the deployment workflow:
   ```bash
   # Navigate to infrastructure
   cd /home/pdiogo/hosted-apps/repos/dashboard-infrastructure

   # Force pull the new image
   docker pull ghcr.io/graphprotocol/rewards-eligibility-oracle-dashboard:latest

   # Force recreate containers
   docker compose up -d --force-recreate reo reo-scheduler

   # Verify new version
   docker exec reo-scheduler-prod python -c "import generate_dashboard; print(generate_dashboard.VERSION)"
   ```

3. **Test production** using the production testing checklist above

---

**Last Updated:** 2026-02-10 (After v0.1.0 deployment, added release workflow docs)
**Deployment Version:** v0.1.0
**Status:** Lessons documented and actionable
