import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { Modal, Platform, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  WebView,
  type WebViewMessageEvent,
  type WebViewNavigation,
} from 'react-native-webview';

import { ThemedText } from '@/components/themed-text';
import { EmptyState } from '@/components/ui';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { draftItem } from '@/state/draft-item';

// 스캔을 시작할 URL. 원하는 쇼핑몰/상품 페이지로 바꿔도 됩니다.
const START_URL = 'https://www.musinsa.com/';

// ── 웹 → 앱 메시지 프로토콜 ──────────────────────────────
type Candidate = { src: string; w: number; h: number };
type ScanMessage =
  | { type: 'IMAGE_CANDIDATES'; payload: Candidate[] }
  | { type: 'LOG'; payload: string };

// 페이지 로드 전에 주입: WebView 안 console.log 를 앱으로 넘겨 디버깅.
const CONSOLE_BRIDGE = `
(function() {
  var orig = console.log;
  console.log = function() {
    try {
      window.ReactNativeWebView.postMessage(JSON.stringify({
        type: 'LOG',
        payload: Array.prototype.slice.call(arguments).join(' ')
      }));
    } catch (e) {}
    orig.apply(console, arguments);
  };
})();
true;
`;

// "자동스캔" 눌렀을 때 주입: 페이지에서 옷 사진 후보(큰 이미지)를 추출.
const IMAGE_SCAN_JS = `
(function() {
  var seen = {};
  var candidates = Array.prototype.slice.call(document.images)
    .filter(function(i) {
      // 로고/아이콘/배너 제외: 일정 크기 이상 + 정사각형~세로형만
      var ratio = i.naturalHeight / i.naturalWidth;
      return i.naturalWidth >= 200 && i.naturalHeight >= 200 && ratio > 0.7;
    })
    .map(function(i) {
      var src = i.currentSrc || i.src; // 이미 절대경로로 정규화되어 있음
      return { src: src, w: i.naturalWidth, h: i.naturalHeight };
    })
    .filter(function(o) {
      if (!o.src || seen[o.src]) return false;
      seen[o.src] = 1;
      return true;
    })
    .sort(function(a, b) { return (b.w * b.h) - (a.w * a.h); }) // 큰 이미지 먼저
    .slice(0, 30);

  console.log('scan found', candidates.length, 'images');
  window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'IMAGE_CANDIDATES', payload: candidates }));
})();
true;
`;

/**
 * 웹 안내 화면.
 * react-native-webview 는 웹을 지원하지 않아(“does not support this platform”) 이 화면이
 * 브라우저에서는 빈 화면 + 빨간 에러로 뜬다. 진입 자체를 막는 대신, 기능이 존재한다는 것과
 * 어디서 쓸 수 있는지를 알려준다.
 */
function ImportUnsupportedOnWeb() {
  return (
    <View style={styles.webNotice}>
      <SafeAreaView edges={['top']} style={styles.webNoticeSafe}>
        <EmptyState
          icon="globe"
          title="가져오기는 앱에서 쓸 수 있어요"
          description={
            '쇼핑몰 페이지를 열어 사진을 자동으로 찾아오는 기능이라\n' +
            'iOS·Android 앱에서만 동작해요. 웹에서는 앨범·카메라·라이브러리로 추가해 주세요.'
          }
          actionLabel="다른 방법으로 추가하기"
          onAction={() => router.replace('/item-add-source')}
        />
      </SafeAreaView>
    </View>
  );
}

export default function ImportScreen() {
  const theme = useTheme();
  const webRef = useRef<WebView>(null);

  const [currentUrl, setCurrentUrl] = useState(START_URL);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [showResults, setShowResults] = useState(false);

  // ③ URL 이 바뀔 때마다 호출 → 지금은 로그만 (나중에 주문내역 페이지 감지에 사용)
  const handleNav = (nav: WebViewNavigation) => {
    setCurrentUrl(nav.url);
    console.log('[NAV]', nav.url);
  };

  // ④ 자동스캔 → 이미지 추출 JS 주입
  const runScan = () => {
    webRef.current?.injectJavaScript(IMAGE_SCAN_JS);
  };

  // ⑤ 웹 → 앱 메시지 수신
  const handleMessage = (e: WebViewMessageEvent) => {
    let msg: ScanMessage;
    try {
      msg = JSON.parse(e.nativeEvent.data);
    } catch {
      return;
    }
    if (msg.type === 'LOG') {
      console.log('[WebView]', msg.payload);
      return;
    }
    if (msg.type === 'IMAGE_CANDIDATES') {
      setCandidates(msg.payload);
      setSelected(new Set());
      setShowResults(true);
      console.log('[SCAN] 후보 이미지', msg.payload.length, '개');
    }
  };

  const toggleSelect = (src: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(src)) next.delete(src);
      else next.add(src);
      return next;
    });
  };

  const confirmSelection = () => {
    // 선택한 첫 번째 사진을 D2 화면으로 전달하고 모달 닫기
    const photo = Array.from(selected)[0];
    console.log('[선택 완료]', Array.from(selected));
    setShowResults(false);
    if (photo) {
      draftItem.setPhoto(photo);
      router.replace('/item-add');
    }
  };

  // WebView 가 웹을 지원하지 않으므로 브라우저에서는 안내 화면으로 대체한다.
  if (Platform.OS === 'web') return <ImportUnsupportedOnWeb />;

  return (
    <View style={styles.container}>
      {/* 상단 바: 취소 + 현재 URL 표시 */}
      <SafeAreaView
        edges={['top']}
        style={[styles.urlBar, { backgroundColor: theme.backgroundElement }]}>
        <Pressable hitSlop={8} onPress={() => router.back()}>
          <ThemedText type="smallBold">취소</ThemedText>
        </Pressable>
        <ThemedText
          type="small"
          numberOfLines={1}
          themeColor="textSecondary"
          style={styles.urlText}>
          {currentUrl}
        </ThemedText>
      </SafeAreaView>

      {/* 인앱 브라우저 */}
      <WebView
        ref={webRef}
        source={{ uri: START_URL }}
        style={styles.webview}
        sharedCookiesEnabled
        thirdPartyCookiesEnabled
        injectedJavaScriptBeforeContentLoaded={CONSOLE_BRIDGE}
        onNavigationStateChange={handleNav}
        onMessage={handleMessage}
        startInLoadingState
      />

      {/* 하단 액션 바 */}
      <SafeAreaView
        edges={['bottom']}
        style={[styles.actionBar, { backgroundColor: theme.background }]}>
        <Pressable
          style={[styles.primaryButton, { backgroundColor: theme.text }]}
          onPress={runScan}>
          <ThemedText style={{ color: theme.background, fontWeight: '600' }}>
            자동스캔
          </ThemedText>
        </Pressable>
      </SafeAreaView>

      {/* 스캔 결과 모달 */}
      <Modal
        visible={showResults}
        animationType="slide"
        onRequestClose={() => setShowResults(false)}>
        <SafeAreaView style={[styles.modal, { backgroundColor: theme.background }]}>
          <View style={styles.modalHeader}>
            <ThemedText type="smallBold">
              이미지 후보 {candidates.length}개 · 선택 {selected.size}
            </ThemedText>
            <Pressable onPress={() => setShowResults(false)}>
              <ThemedText type="small" themeColor="textSecondary">
                닫기
              </ThemedText>
            </Pressable>
          </View>

          <ScrollView contentContainerStyle={styles.grid}>
            {candidates.map((c) => {
              const isSel = selected.has(c.src);
              return (
                <Pressable
                  key={c.src}
                  onPress={() => toggleSelect(c.src)}
                  style={styles.gridItem}>
                  <Image
                    source={{ uri: c.src }}
                    style={[
                      styles.thumb,
                      { borderColor: isSel ? theme.text : theme.backgroundElement },
                    ]}
                    contentFit="cover"
                  />
                </Pressable>
              );
            })}
          </ScrollView>

          <Pressable
            style={[
              styles.primaryButton,
              { backgroundColor: theme.text, margin: Spacing.three, opacity: selected.size ? 1 : 0.4 },
            ]}
            disabled={!selected.size}
            onPress={confirmSelection}>
            <ThemedText style={{ color: theme.background, fontWeight: '600' }}>
              내 옷장에 추가 ({selected.size})
            </ThemedText>
          </Pressable>
        </SafeAreaView>
      </Modal>
    </View>
  );
}

const THUMB_SIZE = '31%';

const styles = StyleSheet.create({
  webNotice: { flex: 1, backgroundColor: '#ffffff' },
  webNoticeSafe: { flex: 1, justifyContent: 'center' },
  container: { flex: 1 },
  urlBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    paddingHorizontal: Spacing.three,
    paddingBottom: Spacing.two,
  },
  urlText: { flex: 1 },
  webview: { flex: 1 },
  actionBar: {
    paddingHorizontal: Spacing.three,
    paddingTop: Spacing.two,
  },
  primaryButton: {
    paddingVertical: Spacing.three,
    borderRadius: Spacing.three,
    alignItems: 'center',
  },
  modal: { flex: 1 },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: Spacing.three,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
    paddingHorizontal: Spacing.three,
  },
  gridItem: { width: THUMB_SIZE, aspectRatio: 0.75 },
  thumb: {
    width: '100%',
    height: '100%',
    borderRadius: Spacing.two,
    borderWidth: 3,
  },
});
