export const PASSWORD_REQUIREMENTS = 'Use at least 8 characters.';
export function newPasswordError(password: string): string {
  if (Array.from(password).length < 8) return PASSWORD_REQUIREMENTS;
  return new TextEncoder().encode(password).length > 72 ? 'Password must not exceed 72 UTF-8 bytes.' : '';
}
