/* Service directory: common business subscriptions with their admin or
   billing page and help center. Picking one in the add form pre-fills
   category and links. Many billing pages live behind a company-specific
   subdomain, so some links land on the closest stable front door. Links
   drift as vendors redesign; each one is a starting point, not a
   guarantee. */

const SERVICE_DIRECTORY = [
  { name: "Slack", category: "Communication",
    links: { manage: "https://my.slack.com/admin/billing", cancel: "", help: "https://slack.com/help" } },
  { name: "Zoom", category: "Communication",
    links: { manage: "https://zoom.us/billing", cancel: "", help: "https://support.zoom.com" } },
  { name: "Microsoft 365", category: "Productivity",
    links: { manage: "https://admin.microsoft.com", cancel: "", help: "https://support.microsoft.com" } },
  { name: "Google Workspace", category: "Productivity",
    links: { manage: "https://admin.google.com", cancel: "", help: "https://support.google.com/a" } },
  { name: "GitHub", category: "Dev Tools",
    links: { manage: "https://github.com/settings/billing", cancel: "", help: "https://docs.github.com/billing" } },
  { name: "Atlassian", category: "Dev Tools",
    links: { manage: "https://admin.atlassian.com", cancel: "", help: "https://support.atlassian.com" } },
  { name: "Notion", category: "Productivity",
    links: { manage: "https://www.notion.so/settings", cancel: "", help: "https://www.notion.com/help" } },
  { name: "Figma", category: "Design",
    links: { manage: "https://www.figma.com/settings", cancel: "", help: "https://help.figma.com" } },
  { name: "Adobe Creative Cloud", category: "Design",
    links: { manage: "https://adminconsole.adobe.com", cancel: "", help: "https://helpx.adobe.com" } },
  { name: "Salesforce", category: "Sales & CRM",
    links: { manage: "https://login.salesforce.com", cancel: "", help: "https://help.salesforce.com" } },
  { name: "HubSpot", category: "Sales & CRM",
    links: { manage: "https://app.hubspot.com", cancel: "", help: "https://knowledge.hubspot.com" } },
  { name: "Asana", category: "Productivity",
    links: { manage: "https://app.asana.com/admin", cancel: "", help: "https://help.asana.com" } },
  { name: "Dropbox Business", category: "Cloud & Storage",
    links: { manage: "https://www.dropbox.com/team/admin", cancel: "", help: "https://help.dropbox.com" } },
  { name: "1Password", category: "Security",
    links: { manage: "https://start.1password.com", cancel: "", help: "https://support.1password.com" } },
  { name: "DocuSign", category: "HR & Legal",
    links: { manage: "https://account.docusign.com", cancel: "", help: "https://support.docusign.com" } },
  { name: "Canva", category: "Design",
    links: { manage: "https://www.canva.com/settings", cancel: "", help: "https://www.canva.com/help" } },
  { name: "ChatGPT Team", category: "AI Tools",
    links: { manage: "https://chatgpt.com/settings", cancel: "", help: "https://help.openai.com" } },
  { name: "Claude Team", category: "AI Tools",
    links: { manage: "https://claude.ai/settings/billing", cancel: "", help: "https://support.claude.com" } },
  { name: "Zapier", category: "Dev Tools",
    links: { manage: "https://zapier.com/app/settings/billing", cancel: "", help: "https://help.zapier.com" } },
  { name: "Mailchimp", category: "Marketing",
    links: { manage: "https://admin.mailchimp.com", cancel: "", help: "https://mailchimp.com/help" } },
  { name: "QuickBooks Online", category: "Finance & Accounting",
    links: { manage: "https://accounts.intuit.com", cancel: "", help: "https://quickbooks.intuit.com/learn-support" } },
  { name: "Xero", category: "Finance & Accounting",
    links: { manage: "https://go.xero.com", cancel: "", help: "https://central.xero.com" } },
  { name: "ElevenLabs", category: "AI Tools",
    links: { manage: "https://elevenlabs.io/app/subscription", cancel: "", help: "https://help.elevenlabs.io" } },
  { name: "n8n Cloud", category: "Dev Tools",
    links: { manage: "https://app.n8n.cloud", cancel: "", help: "https://docs.n8n.io" } }
];

if (typeof window !== "undefined") window.SERVICE_DIRECTORY = SERVICE_DIRECTORY;
