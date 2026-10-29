// Presentation permissions only; Module 2 independently authorizes every mutation.
export function canManageSession(
  userId: string | undefined,
  ownerId: string | null,
  isAdmin = false,
  readOnly = false,
) {
  return !readOnly && Boolean(userId) && (isAdmin || ownerId === userId);
}
