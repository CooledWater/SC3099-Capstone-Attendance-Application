# Enrollment accounts without email invitations

The user explicitly approved removing the documented invitation flow and replacing it with an initial password shown to the enrolling staff member. Files under docs remain read-only.

POST /api/v1/enrollments/bulk still accepts course_id, student_emails and create_accounts. With create_accounts=true, each missing eligible student account receives a distinct cryptographically generated 24-character URL-safe initial password. The password is bcrypt-hashed for storage; its plaintext appears only in that successful response detail as initial_password. The response uses Cache-Control: no-store. Existing and reactivated accounts never have their passwords changed or returned. Duplicate emails are processed once. Batch failures roll back new accounts and enrollments and return no credentials. Existing course authorization and audit behavior are retained; TA accounts remain read-only under the current enrollment contract.

The dashboard's bulk enrollment results show each newly created student's email and initial password. Staff should share it before closing the dialog. Credentials are component state, not query-cache or browser-storage data; results clear on close or course change. They cannot be recovered through repeated enrollment requests. No forced password-change workflow has been added.

Mailpit, SMTP configuration/dependency, the email outbox worker, invitation generation and login blocking, invitation status/resend UI, setup-account route and login invitation link are removed. Retired invitation endpoints return 404. Existing account passwords remain unchanged. Old pending accounts with unknown passwords do not gain a new password automatically; old invitation links no longer work.

No database migration or data deletion is required. Existing account_invitations metadata is left in place but never used for sign-in or email. The privacy deletion worker continues deleting legacy rows if this table exists.

Endpoints removed: GET /api/v1/enrollments/course/{course_id}/invitations; POST /api/v1/enrollments/invitations/resend; POST /api/v1/auth/invitations/{validate,complete,request}. POST /api/v1/auth/login uses the existing password verification directly. Other auth/account contracts remain unchanged.

Checks cover account creation/login with generated credentials, unique passwords, existing credentials, authorization, duplicate/repeated enrollment, rollback, audit secrecy, legacy metadata compatibility, removal of endpoints, UI results and clearing credentials on close. Former invitation-delivery tests are replaced with this behavior; the retired invitation browser test is removed.
