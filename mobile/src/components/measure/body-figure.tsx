import Svg, {
  Circle,
  Ellipse,
  G,
  Line,
  Path,
  Polyline,
  Text as SvgText,
} from 'react-native-svg';

import { Editorial, ink } from '@/constants/theme';
import type { BodyMeasureKey } from '@/constants/body-measures';

/**
 * '어디서부터 어디까지 재는가'를 그림 하나로 보여주는 정면 인체 도식.
 *
 * 항목마다 다른 그림을 그리지 않고 **같은 인체 위에 표시만 바꾼다.** 항목을 옮겨 다녀도
 * 기준이 되는 몸이 그대로라 위치를 비교할 수 있고, 도식을 10장 관리하지 않아도 된다.
 *
 * 표시는 네 종류다.
 *   width    — 두 점 사이 **직선 너비** (어깨너비). 양 끝에 점을 찍어 '어디까지'를 못 박는다.
 *   girth    — 몸을 감는 **둘레**. 점선 타원이라 뒤로 돌아가는 느낌이 난다.
 *   length   — 두 높이 사이 **세로 길이** (목길이).
 *   segments — 두 구간의 **비율**. 구간마다 대괄호를 세우고 ①②로 순서를 밝힌다.
 *
 * 좌표계는 viewBox 200×380 고정이고, 아래 LANDMARK 가 인체와 표시의 단일 출처다.
 * 인체 폴리라인을 고치면 표시 좌표도 같이 고쳐야 한다.
 */

// 인체 기준선 — 표시 좌표는 전부 여기서 끌어다 쓴다.
const SHOULDER_Y = 88;
const SHOULDER_L = 62;
const SHOULDER_R = 138;
const HIP_Y = 214;
const KNEE_Y = 290;
const ANKLE_Y = 356;

/** 몸통 실루엣 — 어깨 → 허리(잘록) → 골반 */
const TORSO_PATH = [
  `M ${SHOULDER_L},${SHOULDER_Y}`,
  'C 66,120 72,142 76,164',
  'C 70,184 68,198 70,214',
  `L 130,${HIP_Y}`,
  'C 132,198 130,184 124,164',
  `C 128,142 134,120 ${SHOULDER_R},${SHOULDER_Y}`,
  'Z',
].join(' ');

const ARM_L = '66,92 54,140 58,196';
const ARM_R = '134,92 146,140 142,196';
const LEG_L = `86,${HIP_Y} 84,${KNEE_Y} 88,${ANKLE_Y}`;
const LEG_R = `114,${HIP_Y} 116,${KNEE_Y} 112,${ANKLE_Y}`;

/** 목 — 아래쪽을 막지 않는다. 가로선을 그으면 몸통 위에 상자가 얹힌 것처럼 보인다 */
const NECK_PATH = 'M 92,50 L 92,90 M 108,50 L 108,90';

const FIGURE_LINE = ink(0.22);
const FIGURE_FILL = ink(0.07);
const MARK = Editorial.ink;

type Highlight =
  | { kind: 'width'; y: number; x1: number; x2: number }
  | { kind: 'girth'; cx: number; cy: number; rx: number; ry: number; tilt?: number }
  | { kind: 'length'; x: number; y1: number; y2: number }
  | { kind: 'segments'; x: number; segments: [number, number][] };

/**
 * 항목별 표시 위치. girth 의 rx 는 그 높이에서의 몸 반폭 + 여유(2~3)로 잡아
 * 줄자가 몸에 걸쳐 보이게 한다.
 */
const HIGHLIGHTS: Record<BodyMeasureKey, Highlight> = {
  shoulder: { kind: 'width', y: SHOULDER_Y, x1: SHOULDER_L, x2: SHOULDER_R },
  chest: { kind: 'girth', cx: 100, cy: 120, rx: 36, ry: 7 },
  waist: { kind: 'girth', cx: 100, cy: 164, rx: 27, ry: 6 },
  hip: { kind: 'girth', cx: 100, cy: 206, rx: 33, ry: 7 },
  thigh: { kind: 'girth', cx: 85, cy: 242, rx: 14, ry: 4.5 },
  calf: { kind: 'girth', cx: 85, cy: 312, rx: 12, ry: 4 },
  // 팔은 비스듬해서 타원도 같이 기울여야 팔을 감은 것처럼 보인다.
  arm: { kind: 'girth', cx: 57, cy: 126, rx: 10, ry: 3.5, tilt: -14 },
  neck_length: { kind: 'length', x: 122, y1: 58, y2: SHOULDER_Y },
  thigh_calf_ratio: {
    kind: 'segments',
    x: 152,
    segments: [
      [HIP_Y, KNEE_Y],
      [KNEE_Y, ANKLE_Y],
    ],
  },
  torso_leg_ratio: {
    kind: 'segments',
    x: 164,
    segments: [
      [SHOULDER_Y, HIP_Y],
      [HIP_Y, ANKLE_Y],
    ],
  },
};

/** 세로 대괄호 — 구간의 시작과 끝을 못 박는다 */
function Bracket({ x, y1, y2, label }: { x: number; y1: number; y2: number; label: string }) {
  const tick = 6;
  return (
    <G>
      <Line x1={x} y1={y1} x2={x} y2={y2} stroke={MARK} strokeWidth={2} />
      <Line x1={x - tick} y1={y1} x2={x + tick} y2={y1} stroke={MARK} strokeWidth={2} />
      <Line x1={x - tick} y1={y2} x2={x + tick} y2={y2} stroke={MARK} strokeWidth={2} />
      <SvgText
        x={x + 10}
        y={(y1 + y2) / 2 + 4}
        fill={MARK}
        fontSize={13}
        fontWeight="600">
        {label}
      </SvgText>
    </G>
  );
}

export function BodyFigure({
  measureKey,
  size = 220,
}: {
  measureKey: BodyMeasureKey;
  size?: number;
}) {
  const highlight = HIGHLIGHTS[measureKey];

  return (
    <Svg width={size} height={size * (380 / 200)} viewBox="0 0 200 380">
      {/* ── 인체 ── 팔·다리를 몸통보다 먼저 그려 어깨·골반 이음매가 몸통에 덮이게 한다 */}
      <Polyline
        points={ARM_L}
        fill="none"
        stroke={FIGURE_LINE}
        strokeWidth={9}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.5}
      />
      <Polyline
        points={ARM_R}
        fill="none"
        stroke={FIGURE_LINE}
        strokeWidth={9}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.5}
      />
      <Polyline
        points={LEG_L}
        fill="none"
        stroke={FIGURE_LINE}
        strokeWidth={16}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.5}
      />
      <Polyline
        points={LEG_R}
        fill="none"
        stroke={FIGURE_LINE}
        strokeWidth={16}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.5}
      />
      <Path d={NECK_PATH} stroke={FIGURE_LINE} strokeWidth={2.5} fill="none" />
      <Path d={TORSO_PATH} fill={FIGURE_FILL} stroke={FIGURE_LINE} strokeWidth={2.5} />
      <Circle cx={100} cy={36} r={19} stroke={FIGURE_LINE} strokeWidth={2.5} fill={FIGURE_FILL} />

      {/* ── 표시 ── */}
      {highlight.kind === 'width' ? (
        <G>
          {/* 끝점을 벗어나는 보조선 — '여기까지'가 어깨 끝임을 눈으로 못 박는다 */}
          <Line
            x1={highlight.x1 - 12}
            y1={highlight.y}
            x2={highlight.x2 + 12}
            y2={highlight.y}
            stroke={ink(0.2)}
            strokeWidth={1}
            strokeDasharray="3 3"
          />
          <Line
            x1={highlight.x1}
            y1={highlight.y}
            x2={highlight.x2}
            y2={highlight.y}
            stroke={MARK}
            strokeWidth={2.5}
          />
          <Line
            x1={highlight.x1}
            y1={highlight.y - 9}
            x2={highlight.x1}
            y2={highlight.y + 9}
            stroke={MARK}
            strokeWidth={2.5}
          />
          <Line
            x1={highlight.x2}
            y1={highlight.y - 9}
            x2={highlight.x2}
            y2={highlight.y + 9}
            stroke={MARK}
            strokeWidth={2.5}
          />
          <Circle cx={highlight.x1} cy={highlight.y} r={4.5} fill={MARK} />
          <Circle cx={highlight.x2} cy={highlight.y} r={4.5} fill={MARK} />
        </G>
      ) : null}

      {highlight.kind === 'girth' ? (
        <Ellipse
          cx={highlight.cx}
          cy={highlight.cy}
          rx={highlight.rx}
          ry={highlight.ry}
          fill="none"
          stroke={MARK}
          strokeWidth={2.5}
          strokeDasharray="5 4"
          origin={`${highlight.cx}, ${highlight.cy}`}
          rotation={highlight.tilt ?? 0}
        />
      ) : null}

      {highlight.kind === 'length' ? (
        <G>
          <Line
            x1={highlight.x - 30}
            y1={highlight.y1}
            x2={highlight.x + 4}
            y2={highlight.y1}
            stroke={ink(0.2)}
            strokeWidth={1}
            strokeDasharray="3 3"
          />
          <Line
            x1={highlight.x - 30}
            y1={highlight.y2}
            x2={highlight.x + 4}
            y2={highlight.y2}
            stroke={ink(0.2)}
            strokeWidth={1}
            strokeDasharray="3 3"
          />
          <Line
            x1={highlight.x}
            y1={highlight.y1}
            x2={highlight.x}
            y2={highlight.y2}
            stroke={MARK}
            strokeWidth={2.5}
          />
          <Line
            x1={highlight.x - 6}
            y1={highlight.y1}
            x2={highlight.x + 6}
            y2={highlight.y1}
            stroke={MARK}
            strokeWidth={2.5}
          />
          <Line
            x1={highlight.x - 6}
            y1={highlight.y2}
            x2={highlight.x + 6}
            y2={highlight.y2}
            stroke={MARK}
            strokeWidth={2.5}
          />
        </G>
      ) : null}

      {highlight.kind === 'segments'
        ? highlight.segments.map(([y1, y2], i) => (
            <Bracket
              key={`${y1}-${y2}`}
              x={highlight.x}
              y1={y1}
              y2={y2}
              label={i === 0 ? '①' : '②'}
            />
          ))
        : null}
    </Svg>
  );
}
