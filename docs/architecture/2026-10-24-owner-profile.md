# Owner account profile, prepared locally

This change extends the existing single owner account. It does not create a
second user table, a new sign-in provider, or a Gmail identity dependency.

## Data and behavior

- Migration 0049 adds first name, last name, phone number, and optional
  photo columns to `users`. Existing login email, display name, password
  hash, Google subject, and all application data are retained.
- The photo is owner-only, stored as a resized JPEG without source metadata.
  Routine user reads defer the binary column. Uploads accept JPG, PNG or
  WebP up to 2 MB and 16 megapixels. The photo is not available to extension
  tokens.
- The owner can update profile fields on Settings. ACE derives the display
  name from first and last name.
- Changing the sign-in email requires the current password and a short-lived
  code sent to the new address. Verification revokes sessions and clears the
  old Google subject. The owner signs in again using the new address. Gmail
  Inbox Intelligence remains a separate connection.

## Release preparation

1. Take the normal encrypted cloud database backup and verify it is readable.
2. Deploy the API and web images together, then run Alembic through 0049
   before accepting traffic on the new API image. No scheduler switch is
   required.
3. Check the owner can sign in and open Settings, update a profile field,
   upload and remove a photo, and that the existing application count is
   unchanged. Send a test email-change code only if the owner intends to
   change their sign-in address.
4. Keep both discovery schedulers in their existing independent comparison
   mode. Do not start the old replica.

## Rollback

Restore the previous API and web images if the release fails. Revision 0049
is additive and can remain installed while the previous app runs. Do not
run the migration downgrade in production because it would discard any
profile fields or photo saved after release. If a database restore is
needed, use the verified pre-release backup and reconcile any intervening
application writes before restoring.
