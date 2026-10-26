export const PASSWORD_REQUIREMENTS = 'Use at least 8 characters, including an uppercase letter, a lowercase letter, and a special character.';
export function newPasswordError(password: string): string {
  if (Array.from(password).length < 8 || !/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/[\x21-\x2F\x3A-\x40\x5B-\x60\x7B-\x7E]/.test(password)) return PASSWORD_REQUIREMENTS;
  return new TextEncoder().encode(password).length > 72 ? 'Password must not exceed 72 UTF-8 bytes.' : '';
}
