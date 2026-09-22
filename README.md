# AI Email Agent for Microsoft Outlook

This local Windows app monitors unread Outlook email, generates contextual reply drafts, and presents every draft in a review dashboard before sending.

## What it does

- Reads unread messages from the Outlook Inbox through Microsoft Graph.
- Classifies messages and skips configured newsletters, promotions, and no-reply senders.
- Creates Outlook reply drafts for messages that need a response.
- Lets the user review, edit, send, discard, delete, and restore drafts.
- Keeps running when the browser tab is closed; it stops only through **Stop Agent**.

## Start the app

Double-click `Open_Dashboard`. The first launch creates the virtual environment and installs dependencies. Later launches start the background agent if necessary and open the dashboard.

Closing the browser does not stop the agent. Double-click `Open_Dashboard` to reopen it. Use **Stop Agent** in the dashboard when monitoring should end.

## Configure Microsoft Outlook

1. In Microsoft Entra, create a public desktop app registration.
2. Support the required organizational or personal Microsoft account types.
3. Add `http://localhost` under **Mobile and desktop applications** and allow public client flows.
4. Add delegated Microsoft Graph permissions `Mail.ReadWrite` and `Mail.Send`.
5. In the dashboard, open **Agent Settings → Accounts**.
6. Enter the Application client ID and use `common` as the tenant unless the organization supplies a tenant ID.
7. Select **Save Microsoft details**, then **Connect Microsoft** and complete sign-in.

An organization may require a Microsoft 365 administrator to approve these delegated permissions.

## Configure the AI provider

Open **Agent Settings → AI and Writing**, select OpenRouter, OpenAI, Google Gemini, or Anthropic, paste the matching API key, and save. OpenRouter uses a provider/model slug such as `google/gemini-2.5-flash`, which can be changed in the same settings section. The current configuration selects OpenRouter; until its key is added, another configured provider may be used as a fallback. AI provider selection is independent of the Outlook mailbox connection.

## Dashboard behavior

The main page is a reply-draft queue, not a complete mailbox. It processes unread Outlook messages that appear to need a reply. Use **Mailbox** to read recent Outlook Inbox messages, including messages already marked as read.

PIN protection is enabled in the current local configuration. Unlock the dashboard before viewing drafts or changing settings. Automatic sending is off unless you explicitly enable it.

When a matching Classic Outlook reply signature exists on this Windows profile, the app appends it to Outlook drafts and includes inline signature images. The review window shows whether a signature match was found for the connected mailbox.

## Sharing

Double-click `Create_Sharing_Package` and send the generated `AI-Email-Agent-Share.zip`. The package excludes `.env`, Outlook authorization tokens, email data, logs, and the local virtual environment. The recipient connects their own Microsoft account after installation.

## Private files

Never share or commit:

- `.env`
- `outlook/token_cache.json`
- `data/`
- `logs/`

## Troubleshooting

| Problem | Resolution |
|---|---|
| Dashboard does not open | Allow the first-run dependency installation to finish, then launch again. |
| Connect Microsoft is disabled | Save a valid Microsoft Application client ID first. |
| Microsoft requests administrator approval | Ask the organization's Microsoft 365 administrator to approve `Mail.ReadWrite` and `Mail.Send`. |
| Main dashboard is empty | New reply drafts are created only from unread messages that need responses. Check **Mailbox** for all recent messages. |
| Authorization expired | Open **Agent Settings → Accounts** and select **Connect Microsoft** again. |

Run automated checks with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```
