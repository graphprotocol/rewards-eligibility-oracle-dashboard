#!/bin/bash
# Build and deployment script for Rewards Eligibility Oracle
# This script builds the Docker image and optionally pushes to GHCR
#
# Usage:
#   ./deploy.sh                    # Build only
#   ./deploy.sh push              # Build and push to registry
#   VERSION=1.0.0 ./deploy.sh push # Build and push with version tag

set -e

# Configuration
IMAGE_NAME="${IMAGE_NAME:-ghcr.io/graphprotocol/rewards-eligibility-oracle}"
VERSION=${VERSION:-$(git rev-parse --short HEAD 2>/dev/null || echo 'dev')}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🍪 REO (Rewards Eligibility Oracle) Build & Deploy"
echo "================================================="
echo "Image: $IMAGE_NAME"
echo "Version: $VERSION"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Error: Docker is not installed${NC}"
    exit 1
fi

# Check if .env exists (warn but don't fail)
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file not found${NC}"
    echo "Runtime configuration will be needed via environment variables"
fi

echo -e "${GREEN}✅ Docker is available${NC}"
echo ""

# Build the image
echo "🔨 Building Docker image..."
echo "docker build -t $IMAGE_NAME:$VERSION -t $IMAGE_NAME:latest ."
docker build -t "$IMAGE_NAME:$VERSION" -t "$IMAGE_NAME:latest" .

echo ""
echo -e "${GREEN}✅ Build complete!${NC}"
echo "Image tags:"
echo "  - $IMAGE_NAME:$VERSION"
echo "  - $IMAGE_NAME:latest"
echo ""

# Push if requested
if [ "$1" = "push" ]; then
    echo "📤 Pushing to registry..."
    docker push "$IMAGE_NAME:$VERSION"
    docker push "$IMAGE_NAME:latest"

    echo ""
    echo -e "${GREEN}✅ Push complete!${NC}"
    echo ""
    echo "To deploy, use the infrastructure repo:"
    echo "  cd ../dashboard-infrastructure"
    echo "  docker compose up -d"
else
    echo "ℹ️  Image built locally. To push, run:"
    echo "  ./deploy.sh push"
    echo ""
    echo "To test locally:"
    echo "  docker run --rm -v \$(pwd)/output:/app/output $IMAGE_NAME:$VERSION"
fi

echo ""
echo "📝 Container usage:"
echo "  One-shot:  docker run --rm $IMAGE_NAME:$VERSION"
echo "  Scheduler: docker run -e REO_SCHEDULER_INTERVAL_MINUTES=5 $IMAGE_NAME:$VERSION python scheduler.py"
