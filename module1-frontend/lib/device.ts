const toBase64 = (value: ArrayBuffer) => btoa(String.fromCharCode(...Array.from(new Uint8Array(value))));

export async function createDeviceFingerprint() {
  const signals = [navigator.userAgent, navigator.language, navigator.platform, screen.width, screen.height].join('|');
  return toBase64(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(signals)));
}
