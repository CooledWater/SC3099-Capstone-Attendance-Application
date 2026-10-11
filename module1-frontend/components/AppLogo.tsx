import Image from 'next/image';

export function AppLogo({ size = 48 }: { size?: number }) {
  return <Image className="app-logo" src="/icon.svg" alt="CCDS Attendance Check-In" width={size} height={size} priority unoptimized/>;
}
