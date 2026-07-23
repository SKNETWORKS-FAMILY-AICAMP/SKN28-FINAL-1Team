import * as ImagePicker from 'expo-image-picker';

async function ensurePermission(kind: 'library' | 'camera'): Promise<boolean> {
  const request =
    kind === 'library'
      ? ImagePicker.requestMediaLibraryPermissionsAsync
      : ImagePicker.requestCameraPermissionsAsync;
  const { status } = await request();
  return status === 'granted';
}

/** 앨범에서 옷 사진 1장 선택 */
export async function pickFromAlbum(): Promise<string | null> {
  if (!(await ensurePermission('library'))) return null;
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    allowsEditing: true,
    aspect: [4, 5],
    quality: 0.9,
  });
  if (result.canceled || !result.assets[0]) return null;
  return result.assets[0].uri;
}

/** 체형측정용 전신 사진 1장 선택 (앨범). 크롭 없이 원본 비율 유지 — 전신이 잘리면 안 되므로. */
export async function pickBodyPhoto(): Promise<string | null> {
  if (!(await ensurePermission('library'))) return null;
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    quality: 0.8,
  });
  if (result.canceled || !result.assets[0]) return null;
  return result.assets[0].uri;
}

/** 카메라로 옷 사진 촬영 */
export async function pickFromCamera(): Promise<string | null> {
  if (!(await ensurePermission('camera'))) return null;
  const result = await ImagePicker.launchCameraAsync({
    allowsEditing: true,
    aspect: [4, 5],
    quality: 0.9,
  });
  if (result.canceled || !result.assets[0]) return null;
  return result.assets[0].uri;
}
