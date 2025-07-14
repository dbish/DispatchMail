# dMail

## Configuration

The daemon service reads several environment variables. Two new values are
used for controlling how far back emails are fetched and where metadata is
stored:

- `LOOKBACK_DAYS` &ndash; number of days to fetch emails on startup if no
  previous timestamp has been recorded. Defaults to `5`.
- `DYNAMODB_META_TABLE` &ndash; DynamoDB table that stores the last processed
  timestamp for each IMAP user. Defaults to `dmail_metadata`.
- `DYNAMODB_USERS_TABLE` &ndash; DynamoDB table containing IMAP credentials for
  all monitored inboxes. Defaults to `dmail_users`.

## Email Filtering and Rule Management

Whitelisting rules for deciding which emails are stored can be managed via the
`/api/whitelist` endpoint. Rules are saved in the metadata table under the
`whitelist_rules` key and may match sender addresses, subject text, or rely on
an LLM classification.

### Automatic Reprocessing

When whitelist rules are updated, the system automatically reprocesses emails from the last `LOOKBACK_DAYS` period to ensure consistency with the new rules:

1. **Removal of non-matching emails**: Emails that no longer pass the new whitelist rules are removed from the database.
2. **Addition of newly matching emails**: Emails that now pass the new rules but were previously filtered out are fetched from Gmail and added to the inbox.
3. **Background processing**: This reprocessing happens in the background without blocking the API response.

This ensures that when users change their filtering rules, they immediately see the correct set of emails in their inbox based on the new criteria.

## LLM Actions

When processing emails, the system's language model can perform several actions
by returning JSON instructions:

- `{"label": "LabelName"}` &ndash; apply the given Gmail label.
- `{"draft": "Reply text"}` &ndash; store a draft reply for human review.
- `{"archive": true}` &ndash; archive the email by removing it from the Inbox.

## MCP Server

An optional MCP (Model Context Protocol) server exposes this functionality for
other AIs. Tools are provided for listing emails, drafting replies, labeling,
and archiving messages. Launch the server with `python daemon-service/mcp/server.py`.
