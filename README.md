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

Whitelisting rules for deciding which emails are stored can be managed via the
`/api/whitelist` endpoint. Rules are saved in the metadata table under the
`whitelist_rules` key and may match sender addresses, subject text, or rely on
an LLM classification.

## LLM Actions

When processing emails, the system's language model can perform several actions
by returning JSON instructions:

- `{"label": "LabelName"}` &ndash; apply the given Gmail label.
- `{"draft": "Reply text"}` &ndash; store a draft reply for human review.
- `{"archive": true}` &ndash; archive the email by removing it from the Inbox.
