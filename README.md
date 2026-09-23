# AI Email Agent for Microsoft Outlook

This local Windows app monitors unread Outlook email, generates contextual reply drafts, and presents every draft in a review dashboard before sending.

## What it does

- Reads unread messages from the Outlook Inbox through Microsoft Graph.
- Classifies messages and skips configured newsletters, promotions, and no-reply senders.
- Creates Outlook reply drafts for messages that need a response.
- Lets the user review, edit, send, discard, delete, and restore drafts.
- Keeps running when the browser tab is closed; it stops only through **Stop Agent**.

## Start the app

After extracting the ZIP, double-click `Install_AI_Email_Agent` once. It automatically downloads the official per-user Python installer when Python is missing, creates the private environment, installs all required components, and opens the dashboard. Internet access is required during this first setup. Administrator access is normally not required.

After setup, double-click `Open_Dashboard`. It starts the background agent if necessary and opens the dashboard. If somebody skips the installer, `Open_Dashboard` automatically starts the same setup when required.

Closing the browser does not stop the agent. Double-click `Open_Dashboard` to reopen it. Use **Stop Agent** in the dashboard when monitoring should end.

## Fresh PC checklist

1. Extract the complete ZIP to a normal folder such as Desktop or Documents.
2. Double-click `Install_AI_Email_Agent`.
3. Wait for the setup window to finish and open the dashboard.
4. In **Agent Settings -> Accounts**, save the Microsoft Application client ID and tenant.
5. Select **Connect Microsoft** and sign in to the Outlook mailbox that should be monitored.
6. In **Agent Settings -> AI and Writing**, paste the chosen AI provider key and save.
7. Optional: set a dashboard PIN in Settings after the app is working.

The first install creates a private blank `.env` file on that PC. Do not copy `.env`, Outlook tokens, or email data from another computer.

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

PIN protection is optional and is configured per computer from Settings. Automatic sending is off unless you explicitly enable it.

When a matching Classic Outlook reply signature exists on this Windows profile, the app appends it to Outlook drafts and includes inline signature images. The review window shows whether a signature match was found for the connected mailbox.

## Sharing

Double-click `Create_Sharing_Package` and send the generated `AI-Email-Agent-Share.zip`. The recipient extracts the ZIP and double-clicks `Install_AI_Email_Agent`; Python and all application components are handled automatically. The package excludes `.env`, Outlook authorization tokens, email data, logs, signatures, and the local virtual environment. The recipient connects their own Microsoft account after installation.

## Private files

Never share or commit:

- `.env`
- `outlook/token_cache.json`
- `data/`
- `logs/`

## Troubleshooting

| Problem | Resolution |
|---|---|
| Dashboard does not open | Extract the complete ZIP, run `Install_AI_Email_Agent`, and allow the first-run download to finish. See `setup.log` in the app folder if it fails. |
| Setup says Python or components could not install | Check internet access, antivirus/firewall prompts, and `setup.log`. The installer downloads Python and Python packages during first setup. |
| Dashboard asks for a PIN on a new PC | Use the latest ZIP. Fresh installs start without a PIN; set a new PIN only after setup is complete. |
| Connect Microsoft is disabled | Save a valid Microsoft Application client ID first. |
| Microsoft requests administrator approval | Ask the organization's Microsoft 365 administrator to approve `Mail.ReadWrite` and `Mail.Send`. |
| Connected account has no mails in dashboard | The main dashboard shows reply drafts, not every mailbox item. Use **Mailbox** to view recent inbox emails. |
| Main dashboard is empty | New reply drafts are created only from unread messages that need responses. Check **Mailbox** for all recent messages. |
| Authorization expired | Open **Agent Settings → Accounts** and select **Connect Microsoft** again. |

Run automated checks with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```
