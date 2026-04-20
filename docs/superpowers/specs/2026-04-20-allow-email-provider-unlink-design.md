# Allow Email Provider Unlink

**Date:** 2026-04-20  
**Status:** Approved

## Problem

Users who register via OAuth (Google, VK, Telegram) and later link an email provider cannot unlink it — the backend unconditionally blocks `DELETE /api/users/me/providers/email` with `"Cannot unlink email provider"`. This restriction was overcautious: it prevents legitimate cleanup while existing guards already protect against losing all access.

## Design

### Approach

Remove the hardcoded email-provider block. Rely on the existing "last provider" guard to prevent lockout. No other changes needed — all invariants are already enforced elsewhere.

### Backend — `backend/app/routers/users.py`

Remove lines 73–78:
```python
# Cannot unlink email provider
if provider_type == ProviderType.email:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Cannot unlink email provider",
    )
```

Update the stale comment on the `len(all_providers) == 1` guard (previously referred to "email is blocked above"):
```python
# Prevent removing the last remaining provider (regardless of type).
if len(all_providers) == 1:
    raise HTTPException(...)
```

After this change the full flow for email unlink is:
1. Validate provider string → `ProviderType.email` ✓
2. Load all providers
3. Find email provider — 404 if not linked
4. Check `len == 1` — 400 if it's the only provider
5. Delete and commit

### Backend — `backend/tests/routers/test_users.py`

- **Convert** `test_delete_email_provider_forbidden` → `test_delete_email_provider_success`: user has email + google providers, expects 204 and `db.delete` called on the email provider.
- **Add** `test_delete_last_email_provider_forbidden`: user has only the email provider, expects 400.

### Frontend — no changes

`canUnlink = user.providers.length > 1` already controls button visibility for all providers uniformly. The unlink button for email is already rendered when multiple providers exist; it will now succeed instead of returning an API error.

### Email verification on re-link

`POST /api/users/me/providers/email` already creates `AuthProvider(email_verified=False)`. After unlinking and re-linking an email, the new record starts unverified — the user must go through the verification flow again. No code change required.

## What does NOT change

| Concern | Status |
|---|---|
| User loses all login access | Blocked by `len == 1` check |
| Re-linked email skips verification | `email_verified=False` by default in `link_email` |
| Frontend shows wrong state | `canUnlink` is already provider-agnostic |
| Password reset after unlink | Reset flow looks up `AuthProvider` by email — if unlinked, provider not found → correct 404 |
