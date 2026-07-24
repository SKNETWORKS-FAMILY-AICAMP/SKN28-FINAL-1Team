import { DesktopLanding } from '@/components/desktop-landing';

/**
 * 데스크톱 웹 랜딩("/landing") — 앱("/")과 분리된 소개 페이지.
 * 앱 URL 은 폭에 관계없이 항상 폰 프레임 앱을 띄우고, 이 라우트만 풀와이드로 뜬다.
 */
export default function Landing() {
  return <DesktopLanding />;
}
