# Agentforce: Publish & Deploy Guide

A complete step-by-step guide to publishing your Agentforce agent and deploying it to a web chat channel in a Salesforce Developer Edition org.

> **Note**: The standard Salesforce Developer Edition does not include Agentforce features. You need either an Agentforce-specific trial org (from [developer.salesforce.com](https://developer.salesforce.com/promotions/orgs/agentforce-edition)) or a Trailhead Playground with Agentforce enabled.

---

## Prerequisites

Before you begin, make sure you have:

- A Salesforce org with Einstein/Agentforce enabled (Trailhead Playground or Agentforce trial org)
- An agent built in Agentforce Builder (e.g., `agentforce101_v1`) with topics and actions configured
- "Manage AI Agents" permission assigned to your user
- An Agent User record (e.g., `EinsteinServiceAgent User`) with the **Einstein Agent User** profile
- Permission Set Licenses assigned to your user:
  - Agentforce (Default)
  - Agentforce Service Agent Builder
  - Einstein Prompt Templates
  - Prompt Template Manager

---

## Step 1: Enable Einstein and Agentforce

1. Go to **Setup** → search for "Einstein Setup"
2. Toggle **Turn on Einstein** to On
3. Refresh your browser
4. Go to **Setup** → search for "Agents" or "Agentforce Agents"
5. Toggle **Agentforce** to On (top-right of the Agentforce Agents page)
6. Verify your agents appear in the list

<!-- Screenshot: Agentforce Agents page with toggle On -->
![Agentforce Agents](screenshots/01-agentforce-agents.png)

---

## Step 2: Enable Einstein Bots

This is a critical step that's easy to miss. Einstein Bots must be enabled for the routing to work.

1. Go to **Setup** → search for "Einstein Bots"
2. Turn the **Einstein Bots** toggle **On**

<!-- Screenshot: Einstein Bots toggle -->
![Einstein Bots](screenshots/02-einstein-bots.png)

---

## Step 3: Verify the Agent User Profile

1. Go to **Setup** → search for "Users"
2. Find the `EinsteinServiceAgent User` (the user assigned to your agent)
3. Click **Edit**
4. Confirm the **Profile** is set to **Einstein Agent User**
5. If not, change it and click **Save**

<!-- Screenshot: Users list showing EinsteinServiceAgent Users with Einstein Agent User profile -->
![Agent User Profile](screenshots/03-agent-user-profile.png)

---

## Step 4: Save, Commit, and Activate Your Agent

1. Open your agent in **Agentforce Builder**
2. Verify your agent definition is complete (topics, actions, instructions)
3. Click **Save** (top-right corner)
4. Click **Commit Version** (next to Save)
5. The agent status changes from "Draft" to **"Version 1 (Active)"**
6. An **AgentID** is assigned and a **Deactivate** button appears

<!-- Screenshot: Agent Builder showing "Version 1 (Active)" with Deactivate button -->
![Agent Active](screenshots/04-agent-active.png)

---

## Step 5: Enable Omni-Channel

1. Go to **Setup** → search for "Omni-Channel Settings"
2. Check **Enable Omni-Channel**
3. Toggle **Enhanced Omni-Channel Routing** to On
4. Click **Save**

<!-- Screenshot: Omni-Channel Settings page -->
![Omni-Channel](screenshots/05-omni-channel.png)


---

## Step 6: Create a Routing Configuration

1. Go to **Setup** → Omni-Channel → **Routing Configurations**
2. Click **New**
3. Fill in:
   - **Routing Configuration Name**: `Agentforce Routing`
   - **Routing Priority**: `1`
   - **Routing Model**: `Most Available`
   - **Units of Capacity**: `1`
4. Click **Save**

<!-- Screenshot: Routing Configuration details -->
![Routing Config](screenshots/06-routing-config.png)

---

## Step 7: Create a Fallback Queue

The Fallback Queue handles conversations when the agent can't resolve them.

1. Go to **Setup** → search for "Queues"
2. Click **New** (small button above the queue list table, to the right)
3. Fill in:
   - **Label**: `Messaging Fallback`
   - **Queue Name**: auto-populates
4. In the **Supported Objects** section:
   - Find **"Messaging Session"** in the Available Objects list
   - Select it and click **Add** to move it to Selected Objects
5. In the **Queue Members** section:
   - Add yourself (or your team) as a member
6. Click **Save**

<!-- Screenshot: New Queue form with Messaging Session in Supported Objects -->
![Fallback Queue](screenshots/07-fallback-queue.png)

---

## Step 8: Enable Messaging and Create a Channel

1. Go to **Setup** → search for "Messaging Settings"
2. Toggle **Messaging** to **On**
3. Click **New Channel** (blue button, top-right)
4. Select **Enhanced Chat** (simplest option — no third-party accounts needed)
5. Click **Next**

<!-- Screenshot: Add a Channel dialog with Enhanced Chat selected -->
![Channel Type](screenshots/08-channel-type.png)

6. Fill in the channel details:
   - **Channel Name**: `Agentforce101 Web Chat`
   - **Developer Name**: auto-populates
   - **Deployment Type**: `Web`
   - **Domain**: your org domain (e.g., `orgfarm-1124a2bced-dev-ed.develop.my.salesforce.com`)
7. Click **Next**

<!-- Screenshot: Channel naming form -->
![Channel Name](screenshots/09-channel-name.png)

8. Configure Channel Routing:
   - **Routing Type**: select **Agentforce Service Agent**
   - **Agentforce Service Agent**: select your agent (e.g., `agentforce101_v1`)
   - **Fallback Queue**: select the `Messaging Fallback` queue you created in Step 7
9. Click **Save**

<!-- Screenshot: Channel Routing with Agentforce Service Agent selected -->
![Channel Routing](screenshots/10-channel-routing.png)

---

## Step 9: Connect the Routing Flow

This is the step that makes the agent actually respond to incoming chats.

1. Open your agent in **Agentforce Builder**
2. Click the **Connections** tab in the left Explorer panel
3. Click **Go to Flow Builder**
4. Find the **"Route to ESA"** flow
5. Edit the **Route Work** element:
   - Set **Route To** → `Agentforce Service Agent`
   - Set **Agentforce Service Agent** → your agent (e.g., `agentforce101_v1`)
6. **Save** and **Activate** the flow
7. Go back to the agent Connections page and refresh — the flow should now appear as assigned

<!-- Screenshot: Flow Builder with Route to ESA flow -->
![Route Flow](screenshots/11-route-flow.png)

---

## Step 10: Create and Publish the Embedded Service Deployment

1. Go to **Setup** → search for "Embedded Service Deployments"
2. Click **New Deployment**
3. Fill in:
   - **Embedded Service Deployment Name**: `Agentforce101_Web`
   - **API Name**: auto-populates
   - **Domain**: your org domain
   - **Messaging Channel**: select `Agentforce101 Web Chat` (created in Step 8)
4. Click **Save**
5. On the deployment settings page, click **Publish** (blue button, top-right)
6. Wait for the banner "We're processing your update" to clear (can take up to 10 minutes)

<!-- Screenshot: Embedded Service Deployment settings with Publish button -->
![Deployment Settings](screenshots/12-deployment-settings.png)

After publishing, you'll see several configuration cards:
- **Settings** — typing indicators, business hours, etc.
- **Branding** — colors, fonts, avatars
- **Pre-Chat** — optional pre-chat form fields
- **Custom Labels** — personalize visitor experience
- **Code Snippet** — JavaScript embed code for your website
- **Test Enhanced Web Chat** — quick test page

---

## Step 11: Deploy to Experience Cloud Site (Recommended)

For a production-ready deployment, use an Experience Cloud site rather than the standalone test page.

1. Go to **Setup** → search for "Digital Experiences" → toggle **On** and set a domain name
2. Go to **Setup** → search for "All Sites"
3. Click **Builder** next to your site (or create a new one)
4. Click the **Components** icon in the site builder
5. Search for **"Embedded Messaging"**
6. Drag and drop it onto your site page
7. Click **Publish** in the site builder
8. Open the published site — the agent chat widget should appear in the bottom-right corner

<!-- Screenshot: Experience Cloud site with Embedded Messaging component -->
![Experience Site](screenshots/13-experience-site.png)

---

## Step 12: Test Your Agent

You have several options for testing:

| Method | How | Best For |
|--------|-----|----------|
| **Preview** | Click "Preview" in Agent Builder | Quick testing during development |
| **Test Enhanced Web Chat** | Click the link on the Embedded Service Deployment page | Testing the full chat widget flow |
| **Experience Cloud Site** | Open your published site and click the chat bubble | Testing the real end-user experience |
| **Testing Center** | Use Simulate in Agent Builder | Running test conversations at volume |

<!-- Screenshot: Agent responding in the chat widget -->
![Agent Chat](screenshots/14-agent-chat.png)


---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Agents are not available. Try again later." | Enable Einstein Bots (Step 2), set up the Route to ESA flow (Step 9), and re-publish the deployment |
| Messaging Channel dropdown is empty | Create a channel in Messaging Settings (Step 8) |
| "Enable Digital Experiences" warning on deployment page | Setup → search "Digital Experiences" → toggle on and set a domain |
| No queues with Messaging Session support | Create a new queue with "Messaging Session" as a supported object (Step 7) |
| Agent not appearing in routing options | Ensure the agent is activated (Step 4) and you have the correct permission sets |
| Connections tab in Agent Builder is empty | Configure the messaging channel and routing flow first (Steps 8-9) |
| Agent User profile is wrong | Edit the EinsteinServiceAgent User and set Profile to "Einstein Agent User" (Step 3) |
| Agentforce toggle not visible in Setup | Your org may not have the Agentforce license — use a Trailhead Playground or Agentforce trial org |

---

## Quick Reference: The Full Flow

```
1. Enable Einstein          → Setup > Einstein Setup > Turn on
2. Enable Einstein Bots     → Setup > Einstein Bots > Turn on
3. Verify Agent User        → Setup > Users > Einstein Agent User profile
4. Activate Agent           → Agent Builder > Save > Commit Version
5. Enable Omni-Channel      → Setup > Omni-Channel Settings > Enable
6. Create Routing Config    → Setup > Omni-Channel > Routing Configurations > New
7. Create Fallback Queue    → Setup > Queues > New (with Messaging Session)
8. Create Messaging Channel → Setup > Messaging Settings > New Channel > Enhanced Chat
9. Connect Routing Flow     → Agent Builder > Connections > Route to ESA flow > Activate
10. Publish Deployment      → Setup > Embedded Service Deployments > Publish
11. Deploy to Site          → Experience Cloud > Add Embedded Messaging > Publish
12. Test                    → Preview in Agent Builder or chat on published site
```

---

## Sources

- [Salesforce Trailhead: Configure Agentforce for Exceptional Service](https://trailhead.salesforce.com/content/learn/projects/quick-start-build-your-first-agent-with-agentforce/configure-an-agentforce-service-agent)
- [SalesforceFAQs: Create and Deploy Agentforce for Service](https://salesforcefaqs.com/create-and-deploy-agentforce-for-service-in-salesforce/)
- [Salesforce Engineering: Agentforce Enhanced Chat](https://engineering.salesforce.com/how-agentforce-enhanced-chat-built-an-agent-first-chat-experience-while-ensuring-easy-migration-for-3000-customers/)
