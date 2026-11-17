#!/usr/bin/env bash
# deploy.sh - Complete local setup & deploy guide for 3D Model Shop Bot
# Run: chmod +x deploy.sh && ./deploy.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     3D Model Shop Bot - Deploy Helper Script                ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ─── Check prerequisites ───
check_cmd() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}❌ Missing: $1${NC}"
        echo "   Install: $2"
        return 1
    fi
    echo -e "${GREEN}✓${NC} $1 found"
    return 0
}

echo -e "${YELLOW}Checking prerequisites...${NC}"
check_cmd git "brew install git / apt install git"
check_cmd python3 "brew install python3 / apt install python3"
check_cmd railway "npm install -g @railway/cli"
check_cmd gh "brew install gh / https://cli.github.com"
echo ""

# ─── Step 1: BotFather ───
echo -e "${BLUE}═══ STEP 1: Create Bots at @BotFather ═══${NC}"
echo ""
echo "Open Telegram and message @BotFather:"
echo ""
echo "  1. /newbot → Name: My 3D Shop → Username: my3dshop_bot"
echo "     → Save the TOKEN as: SHOP_BOT_TOKEN"
echo ""
echo "  2. /newbot → Name: My 3D Shop Admin → Username: my3dshop_admin_bot"
echo "     → Save the TOKEN as: ADMIN_BOT_TOKEN"
echo ""
read -p "Press ENTER when you have both tokens..."

# ─── Step 2: Get your Chat ID ───
echo -e "${BLUE}═══ STEP 2: Get Your Chat ID ═══${NC}"
echo ""
echo "Message @userinfobot in Telegram → it replies with your Chat ID"
echo "Save it as: MY_CHAT_ID"
echo ""
read -p "Press ENTER when you have your Chat ID..."

# ─── Step 3: Create .env ───
echo -e "${BLUE}═══ STEP 3: Create .env file ═══${NC}"
echo ""
read -p "SHOP_BOT_TOKEN: " SHOP_BOT_TOKEN
read -p "ADMIN_BOT_TOKEN: " ADMIN_BOT_TOKEN
read -p "MY_CHAT_ID: " MY_CHAT_ID
read -p "GitHub username: " GH_USER

cat > .env <<EOF
BOT_TOKEN=$SHOP_BOT_TOKEN
ADMIN_BOT_TOKEN=$ADMIN_BOT_TOKEN
ADMIN_CHAT_IDS=$MY_CHAT_ID
ADMIN_BOT_URL=https://admin-bot-production.up.railway.app/notify
TIMEZONE=Europe/Riga
DATA_FILE=/data/orders.json
SHIPPING_BASE_DAYS=3
SHIPPING_PER_COLOR_DAYS=1
SHIPPING_PER_SIZE_DAYS=1
EOF

echo -e "${GREEN}✓ .env created${NC}"
echo ""

# ─── Step 4: GitHub repo ───
echo -e "${BLUE}═══ STEP 4: Create GitHub Repo ═══${NC}"
echo ""
if gh auth status &>/dev/null; then
    echo "GitHub CLI authenticated. Creating repo..."
    gh repo create "$GH_USER/model-shop-bot" --public --source=. --remote=origin --push
else
    echo "Run: gh auth login"
    echo "Then: gh repo create $GH_USER/model-shop-bot --public --source=. --remote=origin --push"
    read -p "Press ENTER after pushing to GitHub..."
fi
echo ""

# ─── Step 5: Railway login ───
echo -e "${BLUE}═══ STEP 5: Railway Login ═══${NC}"
echo ""
railway login
echo ""

# ─── Step 6: Railway project ───
echo -e "${BLUE}═══ STEP 6: Create Railway Project ═══${NC}"
echo ""
echo "Creating project from GitHub..."
railway init --name model-shop-bot
railway up --detach
echo ""
echo "Waiting for first deploy..."
sleep 10
railway status
echo ""

# ─── Step 7: Add admin bot service ───
echo -e "${BLUE}═══ STEP 7: Add Admin Bot Service ═══${NC}"
echo ""
railway service create --name admin-bot --repo "$GH_USER/model-shop-bot"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: Go to Railway Dashboard → admin-bot → Settings → Build${NC}"
echo -e "${YELLOW}   Set 'Dockerfile Path' to: Dockerfile.admin${NC}"
echo -e "${YELLOW}   Then click 'Deploy'${NC}"
echo ""
read -p "Press ENTER after setting Dockerfile Path and deploying admin-bot..."

# ─── Step 8: Get admin bot URL ───
echo -e "${BLUE}═══ STEP 8: Get Admin Bot URL ═══${NC}"
ADMIN_URL=$(railway domain --service admin-bot 2>/dev/null | head -1)
if [[ -z "$ADMIN_URL" ]]; then
    echo "Get admin bot URL from Railway dashboard (Settings → Domains)"
    read -p "Admin bot URL (e.g., https://admin-bot-xxxx.railway.app): " ADMIN_URL
fi
ADMIN_NOTIFY_URL="${ADMIN_URL}/notify"
echo "Admin notify URL: $ADMIN_NOTIFY_URL"
echo ""

# ─── Step 9: Set variables ───
echo -e "${BLUE}═══ STEP 9: Set Environment Variables ═══${NC}"
echo ""

# Shop bot vars
railway variables set --service shop-bot \
    BOT_TOKEN="$SHOP_BOT_TOKEN" \
    ADMIN_BOT_TOKEN="$ADMIN_BOT_TOKEN" \
    ADMIN_CHAT_IDS="$MY_CHAT_ID" \
    ADMIN_BOT_URL="$ADMIN_NOTIFY_URL" \
    TIMEZONE="Europe/Riga" \
    DATA_FILE="/data/orders.json" \
    SHIPPING_BASE_DAYS="3"

# Admin bot vars
railway variables set --service admin-bot \
    BOT_TOKEN="$ADMIN_BOT_TOKEN" \
    ADMIN_BOT_TOKEN="$ADMIN_BOT_TOKEN" \
    ADMIN_CHAT_IDS="$MY_CHAT_ID" \
    ADMIN_BOT_URL="$ADMIN_NOTIFY_URL" \
    TIMEZONE="Europe/Riga" \
    DATA_FILE="/data/orders.json" \
    SHIPPING_BASE_DAYS="3"

echo -e "${GREEN}✓ Variables set${NC}"
echo ""

# ─── Step 10: Redeploy both ───
echo -e "${BLUE}═══ STEP 10: Redeploy Both Services ═══${NC}"
railway up --service shop-bot --detach
railway up --service admin-bot --detach
echo ""
echo "Waiting for deploys..."
sleep 15
railway status
echo ""

# ─── Step 11: Get shop bot URL ───
echo -e "${BLUE}═══ STEP 11: Your Bot Links ═══${NC}"
SHOP_URL=$(railway domain --service shop-bot 2>/dev/null | head -1)
if [[ -z "$SHOP_URL" ]]; then
    SHOP_URL="https://t.me/your_bot_username"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    🎉 DEPLOY COMPLETE!                       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Open your shop bot:${NC}"
echo -e "  ${BLUE}https://t.me/YOUR_BOT_USERNAME${NC}  (replace with your @BotFather username)"
echo ""
echo -e "${YELLOW}Admin bot:${NC}"
echo -e "  ${BLUE}$ADMIN_URL${NC}"
echo ""
echo -e "${YELLOW}Test flow:${NC}"
echo "  1. Open shop bot → /start"
echo "  2. Browse → select product → color/size/qty → confirm"
echo "  3. Open admin bot → /pending → approve → pick shipping days"
echo "  4. Check shop bot → you get ship date notification"
echo ""
echo -e "${YELLOW}Logs:${NC}"
echo "  railway logs --service shop-bot"
echo "  railway logs --service admin-bot"