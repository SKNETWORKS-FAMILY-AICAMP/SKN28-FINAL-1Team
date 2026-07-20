import { Platform } from 'react-native';

const PINTEREST_REFERER = 'https://www.pinterest.com/';

/** Pinterest·핫링크 차단 URL을 앱에서 로드 가능하게 변환 */
export function getImageSource(uri: string | null | undefined) {
  if (!uri) return null;

  if (uri.includes('pinimg.com')) {
    // Pinterest는 localhost Referer를 거부 → 웹에선 프록시 경유 (목업·데모용)
    if (Platform.OS === 'web') {
      return {
        uri: `https://images.weserv.nl/?url=${encodeURIComponent(uri)}`,
      };
    }
    return {
      uri,
      headers: {
        Referer: PINTEREST_REFERER,
        'User-Agent': 'Mozilla/5.0 (compatible; CozyApp/1.0)',
      },
    };
  }

  return { uri };
}
