# Phase 4: Deployment Channels — Implementation Guide

## Overview

Phase 4 makes the WA_P1to5_Advisor agent accessible to end users through three channels:
- **Web Chat** — Embedded chat widget on an Experience Cloud site
- **Slack** — @mention the agent in Slack channels
- **Mobile** — Salesforce Mobile App with Agentforce tab

All three channels connect to the same agent and Data Cloud backend.

---

## 4A. Web Chat — Experience Cloud Portal with Agentforce

This is the primary deployment channel. It creates a branded "Wealth Advisor Portal" where advisors (or clients) can chat with the agent via a web browser.

### What Gets Deployed Programmatically

These components are deployed via CLI (already done):

| Component | Status | Purpose |
|-----------|--------|---------|
| CORS Whitelist | ✅ Deployed | Allows chat widget to communicate with Salesforce |
| CSP Trusted Site | ✅ Deployed | Content Security Policy for the portal site |
| Network (site) | ✅ Created | Experience Cloud site "Wealth Advisor Portal" |
| Internal User Login | ✅ Enabled | Allows Salesforce users to log into the portal |

### What Requires UI Configuration

The following steps must be done in the Salesforce Setup UI. They cannot be automated via CLI or metadata API.

---

### Step 1: Enable ExperienceBundle Metadata API (one time)

This enables programmatic editing of site branding in the future.

1. Setup → Quick Find → **"Digital Experiences"** → **Settings**
2. Check **"Enable ExperienceBundle Metadata API"**
3. Click **Save**

---

### Step 2: Open Experience Builder and Customize Branding

The Help Center template ships with "Capricorn Coffee" sample branding. Replace it with Wealth Advisor branding.

1. Setup → Quick Find → **"All Sites"** → **Digital Experiences → All Sites**
2. Find **"Wealth Advisor Portal"** → click **"Builder"** (opens Experience Builder)
3. In Experience Builder:

#### 2a. Update the Site Header
- Click the **header area** (top of the page with the logo/site name)
- In the properties panel on the right:
  - **Site Name:** `Wealth Advisor`
  - **Logo:** Upload a professional wealth management logo (or remove the Capricorn Coffee logo)
  - **Tagline:** `Your AI-Powered Financial Assistant`

#### 2b. Update Theme Colors
- Click the **paintbrush icon** (🎨) in the left sidebar → **Theme**
- Update these colors for a professional wealth management look:

| Property | Value | Notes |
|----------|-------|-------|
| Primary Color | `#1B5E20` | Dark green — wealth management standard |
| Secondary Color | `#004D40` | Teal accent |
| Text Color | `#212121` | Near-black for readability |
| Background Color | `#FAFAFA` | Light gray, clean look |
| Header Background | `#1B5E20` | Matches primary |
| Header Text Color | `#FFFFFF` | White on dark green |
| Footer Background | `#263238` | Dark charcoal |
| Footer Text Color | `#B0BEC5` | Light gray |

#### 2c. Update the Hero Banner
- Click the **hero/banner section** on the home page
- Change the heading text: `Welcome to Wealth Advisor`
- Change the subheading: `Ask me about your portfolio, goals, meetings, compliance, and more.`
- Update the background: solid color `#1B5E20` or a professional financial image
- Remove any Capricorn Coffee imagery

#### 2d. Update the Footer
- Click the **footer area**
- Change copyright text: `© 2026 Wealth Advisor Portal — Powered by Agentforce`
- Remove any Capricorn Coffee references

#### 2e. Update the Search Placeholder
- Click the **search bar** component
- Change placeholder text: `Ask the Wealth Advisor...`

---

### Step 3: Configure AI Experiences (Connect Agent to Site)

This is the critical step that makes the chat widget appear.

1. Go back to the **Experience Cloud Workspaces** for the site:
   - Setup → Digital Experiences → All Sites → click **"Workspaces"** next to "Wealth Advisor Portal"
2. In the Workspaces dashboard, click the **"AI Experiences"** tile (blue star icon)
3. Configure:
   - **Share search queries with Agentforce Service Agent:** Toggle **ON** ✅
   - **Share Data Category Selection:** Toggle **ON** ✅
   - **Default AI Agent:** Select **"WA P1to5 Advisor"** from the dropdown
4. Click **Save**

> This connects the agent to the site. The chat widget should now appear when you visit the portal.

---

### Step 4: Publish the Site

1. In Experience Builder (or Workspaces → Administration):
   - Click **"Publish"** (top right in Experience Builder)
   - Or: Workspaces → Administration → Settings → **Publish**
2. Wait 1-2 minutes for the publish to complete
3. Your site is live at:
   ```
   https://<your-domain>.develop.my.site.com/WAP1to5Advisor/s/
   ```

---

### Step 5: Test the Chat Widget

1. Open the site URL in an **incognito/private browser window**:
   ```
   https://<your-domain>.develop.my.site.com/WAP1to5Advisor/s/
   ```
2. You should see the branded Wealth Advisor portal with a **chat icon** (bottom right)
3. Click the chat icon
4. Type: **"Tell me about the Johnson household"**
5. Verify the agent responds with Data Cloud data (Johnson Family, $2.8M AUM, etc.)
6. Try more queries:
   - "How is Wei Chen's portfolio?"
   - "Prep me for my meeting with Raj Patel"
   - "Does Sarah Johnson need rebalancing?"
   - "Transfer me to a specialist"

### Troubleshooting

| Problem | Solution |
|---------|----------|
| Chat widget doesn't appear | Check AI Experiences is configured (Step 3). Verify the agent is activated. |
| Widget appears but spins/errors | Check CORS whitelist (Setup → CORS). Your site URL must be listed. |
| "Access Denied" on the portal | Enable internal user login on the Network. Check guest user profile permissions. |
| Agent doesn't respond | Verify agent is activated (Setup → Agents → WA P1to5 Advisor → must show "Active"). |
| Still shows Capricorn Coffee | You need to customize in Experience Builder (Step 2). Publish after changes. |
| Site shows 404 | Make sure the site status is "Live" (Workspaces → Administration → Activate). |

---

### Alternative: Agent Builder Preview (Quickest — No Setup Needed)

For demos and testing, skip all the above and use the built-in preview:

1. `sf org open --target-org new-org`
2. Setup → Agents → **WA P1to5 Advisor**
3. Click **"Preview"** (top right)
4. Type queries directly — works immediately with no channel setup

---


## 4B. Slack Integration

### What This Enables
Advisors query the agent directly from Slack:
- `@WealthAdvisor prep me for my 2pm with Raj Patel`
- `@WealthAdvisor how is Wei Chen's portfolio doing?`

### Prerequisites
- Slack Business+ or Enterprise plan
- Salesforce for Slack app installed
- Agentforce enabled in org

### Setup Steps

#### Step 1: Install Salesforce for Slack
1. Setup → Quick Find → **"Slack"** → **Getting Started**
2. Click **"Connect to Slack"**
3. Authorize the Salesforce for Slack app in your Slack workspace
4. Verify: Setup → Slack → Slack Apps shows "Connected"

#### Step 2: Enable Agentforce for Slack
1. Setup → Quick Find → **"Agents"** → **Agent Settings**
2. Under **Deployment Channels**, toggle **Slack** to **Enabled**
3. Select agent: **WA P1to5 Advisor**
4. Configure:
   - Slack App Name: `WealthAdvisor`
   - Bot Display Name: `Wealth Advisor`
   - Default Response Visibility: **Only visible to requester** (data privacy)

#### Step 3: Create Dedicated Channels
Recommended:

| Channel | Purpose | Access |
|---------|---------|--------|
| `#wealth-advisor-queries` | General advisor queries | All advisors |
| `#wa-meeting-prep` | Meeting prep requests | All advisors |
| `#wa-compliance-alerts` | Compliance results | Compliance team |

#### Step 4: Test in Slack
1. Open `#wealth-advisor-queries`
2. Type: `@WealthAdvisor Tell me about the Chen household`
3. Verify the agent responds in a thread with Data Cloud data

### Security Notes
- Set default response visibility to "Only visible to requester" for channels with mixed audiences
- Slack users must be mapped to Salesforce users — agent respects sharing rules
- All interactions logged via WA_Audit_Log__c

---

## 4C. Mobile (Salesforce Mobile App)

### What This Enables
Advisors access the agent from the Salesforce Mobile App on iOS/Android for on-the-go meeting prep and client lookups.

### Setup Steps

#### Step 1: Enable Agentforce in Mobile
1. Setup → Quick Find → **"Salesforce Mobile App"** → **Mobile Navigation**
2. Add **"Agentforce"** to the mobile navigation menu
3. Position it near the top for easy access

#### Step 2: Configure Mobile Agent Access
1. Setup → Quick Find → **"Agents"** → **Agent Settings**
2. Under **Deployment Channels**, toggle **Salesforce Mobile** to **Enabled**
3. Select agent: **WA P1to5 Advisor**
4. Configure:
   - Mobile Display Name: `Wealth Advisor`
   - Persistent Chat: **Enabled**

#### Step 3: Test on Mobile
1. Install **Salesforce Mobile App** from App Store / Google Play
2. Log in with your Salesforce credentials
3. Tap the **Agentforce** icon in the navigation
4. Type: "Tell me about Wei Chen"
5. Verify response renders correctly on mobile

### Mobile Considerations

| Item | Details |
|------|---------|
| Offline | Agent requires network connectivity — no offline mode |
| Response Length | Long responses may require scrolling; agent uses bullet points |
| Data Cloud Latency | CdpQuery responses may take 2-5 seconds on mobile networks |
| Authentication | Uses mobile app's existing Salesforce session |
| Voice Input | Mobile keyboard supports voice-to-text |

---

## Deployment Channel Matrix

| Channel | Setup Complexity | Best For | Programmatic? |
|---------|-----------------|----------|---------------|
| **Agent Preview** | None | Demos, testing | N/A (built-in) |
| **Web Chat** (Experience Cloud) | Medium | Client portal, advisor desktop | Partial (CORS/CSP via CLI, rest UI) |
| **Slack** | Low | Quick advisor queries, team collab | UI only |
| **Mobile** | Low | On-the-go meeting prep | UI only |

---

## Deployed Metadata (Programmatic)

```
force-app/main/default/
  corsWhitelistOrigins/
    WA_Portal_Site.corsWhitelistOrigin-meta.xml    # CORS for chat widget
  cspTrustedSites/
    WA_Portal_Site.cspTrustedSite-meta.xml         # CSP for portal site
```

These are deployed automatically with `sf project deploy start --source-dir force-app`.

> **Note:** The CORS URL is org-specific. For a new org, update the URL in both files to match your org's site domain before deploying.

---

## Reproducibility Notes

For a new org deployment:

1. Deploy all metadata first (objects, classes, agent, etc.)
2. Create the Experience Cloud site via UI:
   ```
   Setup → Digital Experiences → All Sites → New → Help Center template
   Name: "Wealth Advisor Portal"
   URL: "WAP1to5Advisor"
   ```
3. Update CORS/CSP files with your org's site URL, then deploy:
   ```bash
   sf project deploy start --source-dir force-app/main/default/corsWhitelistOrigins
   sf project deploy start --source-dir force-app/main/default/cspTrustedSites
   ```
4. Follow Steps 2-5 above to customize branding and connect the agent
5. Publish the site

The Experience Cloud site creation and branding customization are 100% UI operations. There is no CLI equivalent for creating sites or modifying Experience Builder themes.
