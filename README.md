# dMail

## Configuration

The daemon service reads several environment variables. Two new values are
used for controlling how far back emails are fetched and where metadata is
stored:

- `LOOKBACK_DAYS` &ndash; number of days to fetch emails on startup if no
  previous timestamp has been recorded. Defaults to `5`.
- `DYNAMODB_META_TABLE` &ndash; DynamoDB table that stores the last processed
  timestamp for each IMAP user. Defaults to `dmail_metadata`.
