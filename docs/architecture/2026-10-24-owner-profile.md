# Owner account profile, deployed 2026-10-24

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

1. Take a private mode 600 cloud database backup and verify it is readable.
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

Rebuild the previous API and web images from deployed commit
`d1202fd1e590bc290e88c059109bb35ff114796c` if an application rollback
is needed. Revision 0049 is additive and can remain installed while the
previous app runs. Do not run the migration downgrade in production because
it would discard any profile fields or photo saved after release. If a
database restore is needed, use the verified pre-release backup
`private-backups/ace-pre-owner-profile-20261024T215213Z.dump.gz` and
reconcile any intervening application writes before restoring.

## Production verification

The exact release commit is `11a7fd4c74e3333ea76c4fe1e9eecba0615279c6`.
Migration 0049 exited zero. The public health endpoint and version header
matched this SHA. Both schedulers remained healthy, and the Oracle scheduler
retained its previous container ID. One owner, 871 applied job marks, and 47
external application records remained. Private account endpoints returned
401 to anonymous requests. The owner's authenticated production session was
not used for post-release profile interaction checks.
