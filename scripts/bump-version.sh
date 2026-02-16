#!/usr/bin/env bash
# Version Bump Script for cAI-png
# Usage: ./scripts/bump-version.sh [major|minor|patch]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_usage() {
  cat <<EOF
${BLUE}cAI-png Version Bump Utility${NC}

Usage: $0 [major|minor|patch] [OPTIONS]

Version Types:
  major     Bump major version (X.0.0) - Breaking changes
  minor     Bump minor version (0.X.0) - New features
  patch     Bump patch version (0.0.X) - Bug fixes

Options:
  -m, --message   Custom commit message (default: auto-generated)
  -n, --no-commit Don't create git commit
  -h, --help      Show this help message

Examples:
  $0 patch                    # Bump patch version (1.0.0 -> 1.0.1)
  $0 minor                    # Bump minor version (1.0.1 -> 1.1.0)
  $0 major -m "Breaking API"  # Bump major with custom message
  $0 patch --no-commit        # Bump patch without committing

EOF
}

# Parse arguments
BUMP_TYPE=""
COMMIT_MESSAGE=""
NO_COMMIT=false

while [[ $# -gt 0 ]]; do
  case $1 in
    major|minor|patch)
      BUMP_TYPE="$1"
      shift
      ;;
    -m|--message)
      COMMIT_MESSAGE="$2"
      shift 2
      ;;
    -n|--no-commit)
      NO_COMMIT=true
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      print_usage
      exit 1
      ;;
  esac
done

if [ -z "$BUMP_TYPE" ]; then
  echo -e "${RED}Error: Version type required${NC}\n"
  print_usage
  exit 1
fi

cd "$ROOT_DIR"

# Check if working directory is clean
if [ "$NO_COMMIT" = false ]; then
  if ! git diff-index --quiet HEAD --; then
    echo -e "${YELLOW}Warning: Working directory has uncommitted changes${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      exit 1
    fi
  fi
fi

# Get current versions
BACKEND_VERSION=$(node -p "require('./backend/package.json').version")
FRONTEND_VERSION=$(node -p "require('./frontend/package.json').version")

echo -e "${BLUE}Current Versions:${NC}"
echo "  Backend:  v$BACKEND_VERSION"
echo "  Frontend: v$FRONTEND_VERSION"
echo

# Parse version and bump
IFS='.' read -r -a VERSION_PARTS <<< "$BACKEND_VERSION"
MAJOR="${VERSION_PARTS[0]}"
MINOR="${VERSION_PARTS[1]}"
PATCH="${VERSION_PARTS[2]}"

case $BUMP_TYPE in
  major)
    MAJOR=$((MAJOR + 1))
    MINOR=0
    PATCH=0
    ;;
  minor)
    MINOR=$((MINOR + 1))
    PATCH=0
    ;;
  patch)
    PATCH=$((PATCH + 1))
    ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"

echo -e "${GREEN}New Version: v$NEW_VERSION${NC}"
echo

# Update backend package.json
echo -e "${BLUE}Updating backend/package.json...${NC}"
if command -v jq &> /dev/null; then
  jq --arg ver "$NEW_VERSION" '.version = $ver' backend/package.json > backend/package.json.tmp
  mv backend/package.json.tmp backend/package.json
else
  # Fallback to sed if jq not available
  sed -i.bak "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" backend/package.json
  rm -f backend/package.json.bak
fi

# Update frontend package.json
echo -e "${BLUE}Updating frontend/package.json...${NC}"
if command -v jq &> /dev/null; then
  jq --arg ver "$NEW_VERSION" '.version = $ver' frontend/package.json > frontend/package.json.tmp
  mv frontend/package.json.tmp frontend/package.json
else
  sed -i.bak "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" frontend/package.json
  rm -f frontend/package.json.bak
fi

echo -e "${GREEN}✅ Version bumped to v$NEW_VERSION${NC}"
echo

# Git commit
if [ "$NO_COMMIT" = false ]; then
  if [ -z "$COMMIT_MESSAGE" ]; then
    COMMIT_MESSAGE="chore(release): bump version to v$NEW_VERSION"
  fi
  
  echo -e "${BLUE}Creating git commit...${NC}"
  git add backend/package.json frontend/package.json
  git commit -m "$COMMIT_MESSAGE

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
  
  echo -e "${GREEN}✅ Committed with message: $COMMIT_MESSAGE${NC}"
  echo
  
  # Ask if user wants to push
  read -p "Push to origin? (y/N) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}Pushing to origin...${NC}"
    git push origin main
    echo -e "${GREEN}✅ Pushed to origin/main${NC}"
    echo
    echo -e "${YELLOW}🚀 GitHub Actions will now create release v$NEW_VERSION${NC}"
    echo -e "${BLUE}🔗 https://github.com/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/actions${NC}"
  fi
else
  echo -e "${YELLOW}ℹ️  Version updated but not committed (--no-commit flag)${NC}"
fi

echo
echo -e "${GREEN}✨ Done!${NC}"
