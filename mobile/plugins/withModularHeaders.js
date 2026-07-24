const { withDangerousMod } = require('@expo/config-plugins');
const fs = require('fs');
const path = require('path');

/**
 * Podfile 최상단에 `use_modular_headers!` 를 넣는다.
 *
 * 왜: @react-native-google-signin/google-signin 이 의존하는 GoogleSignIn(7+) →
 * AppCheckCore 가 GoogleUtilities/RecaptchaInterop 의 module map 을 요구해서,
 * 기본 static 라이브러리 통합에서 `pod install` 이 실패한다.
 * use_frameworks! 로 링크 방식을 통째로 바꾸면 카카오/네이버 SDK 빌드에 영향이 커서,
 * 링크 방식은 그대로 두고 module map 만 생성하는 use_modular_headers! 를 쓴다.
 *
 * ios/ 는 prebuild 로 재생성되는 gitignore 대상이라, 이 값을 코드에 남기려면 config plugin 이 필요하다.
 */
module.exports = function withModularHeaders(config) {
  return withDangerousMod(config, [
    'ios',
    (config) => {
      const podfilePath = path.join(
        config.modRequest.platformProjectRoot,
        'Podfile',
      );
      let contents = fs.readFileSync(podfilePath, 'utf8');
      if (!contents.includes('use_modular_headers!')) {
        contents = contents.replace(
          /(platform :ios.*\n)/,
          '$1use_modular_headers!\n',
        );
        fs.writeFileSync(podfilePath, contents);
      }
      return config;
    },
  ]);
};
