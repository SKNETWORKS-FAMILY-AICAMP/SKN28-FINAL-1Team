// .svg 를 default import 하면 <SvgProps> 를 받는 React 컴포넌트로 취급한다.
// (metro 의 react-native-svg-transformer 설정과 짝을 이룬다.)
declare module '*.svg' {
  import type { FC } from 'react';
  import type { SvgProps } from 'react-native-svg';

  const content: FC<SvgProps>;
  export default content;
}
