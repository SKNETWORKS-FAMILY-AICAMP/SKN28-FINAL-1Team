# Drive 이미지 + 계절별 색상 팔레트

> **Drive 골든셋 이미지 색상** + **실제 시장 계절별 선호 색상** 통합 가이드
> 작성: 2026-08-07 / Drive 폴더 ID: `178wPfnaVOwRrOyKjOMvTSNE_wtFBCShy`

---

## 1. Drive 골든셋 이미지 폴더 구조

### 1.1. 5명 × 12 카테고리 = 12개 하위 폴더

| 멤버 | 폴더 ID | 성별 카테고리 | 하위 폴더 ID | 파일 수 | 비고 |
|------|---------|----------------|-------------|--------|------|
| **김민욱** | `1spV29pDJS9HCgbYCmTewYPHFP58SPOfl` | men | `16WtXw0NUl1XUKPwSsxmU3z0hQ9xoGPZJ` | 14 | 7/27 수정 |
| | | women | `1bi6UP_FuYVH022swaLa478R2A6JmldGk` | 8 | 7/27 수정 |
| **박건우** | `1Izg3tcUFT2sYCqgDGH6d3NlvnQ8gBS73` | gpt-image-2 | `1yUoWo-pPgg6sfvcCfGRdye1ap0Hw50BS` | 9 | 7/26 수정 |
| | | 남성 | `11sD2gO9IXYOQBze7SWc-uQXccn28CasJ` | 21 | 7/24 수정 |
| | | 여성 | `1zuFv11lP-_6wVte3cNDQ-9bQobxTGyJ9` | 18 | 7/24 수정 |
| **신혜지** | `1QnJeSLAqV4y4FFWkZpqcyTEykmVoDPuU` | 남자 | `1zYk65KEJSeJ6iEOxgjpo6MF7oLqHs6Pv` | 9 | 7/28 수정 |
| | | 여자 | `1v6GnG2IvZgAyQgqfUXN1rzFLWJsofio4` | 22 | 7/28 수정 |
| **이건우** | `1b2dj8XarOYXs64tBmQpnC7tjrv7xbYXZ` | 남성 | `1FO9GmUTswA_WRqZXpi-WmwYTpYeyEqCD` | 75 | 7/23 수정 (가장 많음) |
| | | 여성 | `1RrgyjaloE6Gevf-mOIDb__7wj-x4ibsh` | - | 7/23 수정 |
| **전하영** | `1eWh08xHI0NsPhLDRHSTUkwx6OvhGz10T` | men | `1EKt92XOjWPWuk4wmpCdddiGbqMmAdjEr` | 44 | 7/27 수정 |
| | | women | `1RK0qIieySZcMOl8L4CSpGMizOd0UHOn9` | - | 7/27 수정 |

**총 이미지 추정**: 200+ 장 (Drive 접근 권한 필요)

### 1.2. 카테고리 매핑

| Drive 카테고리 | 우리 시스템 | 비고 |
|----------------|------------|------|
| men / 남자 / 남성 | 남성 코디 추천 | top + pants + outer |
| women / 여자 / 여성 | 여성 코디 추천 | top + pants + dress + outer |
| gpt-image-2 | AI 생성 코디 (실제 시장 트렌드) | 별도 처리 |

---

## 2. Drive 색상 추출 파이프라인 (구현 가이드)

### 2.1. 자동 색상 추출 (ML 파이프라인)
```python
# ml/indexer/util/fashion_siglip.py 활용
from fashion_siglip import FashionSigLIP
import numpy as np

def extract_color_palette(drive_folder_id, limit=100):
    """Drive 폴더에서 색상 추출"""
    # 1. Drive API로 폴더 내 이미지 다운로드 (OAuth 필요)
    files = list_drive_files(drive_folder_id, limit=limit)
    
    # 2. 각 이미지에서 dominant color 5개 추출
    palette = []
    for f in files:
        img = load_image(f.path)
        siglip = FashionSigLIP()
        colors = siglip.extract_palette(img, n_colors=5)
        palette.append({
            'file': f.name,
            'colors': [{'hex': c.hex, 'name': c.name, 'pct': c.percentage} for c in colors]
        })
    
    # 3. 모든 이미지의 색상 통합 + 클러스터링
    return cluster_and_rank(palette)
```

### 2.2. Drive → 17색 매핑

| Drive 색상 (추정) | 우리 17색 | 카테고리 | 비고 |
|------------------|----------|----------|------|
| Black / Black | Black | NEUTRAL | 32-38% 압도적 |
| White | Pure White | NEUTRAL | 15-30% |
| Navy / Dark Blue | Navy | NEUTRAL | 남성 정장 |
| Blue / Medium Blue | Denim | NEUTRAL | 청바지 |
| Gray | Medium Gray | NEUTRAL | 9% |
| Beige | Beige | NEUTRAL | 23% (지그재그 2위) |
| Cream / Off-white | Ivory/Cream | NEUTRAL | 베이지 변형 |
| Brown | Brown | WARM | earth tone |
| Khaki | Khaki | MUTED | 카고 |
| Burgundy / Wine | Burgundy | WARM | 가을/겨울 |
| Olive | Olive | WARM | 545%↑ |
| Mustard | Mustard | WARM | autumn |
| Rust | Rust | WARM | autumn |
| Coral | Coral | WARM | spring |
| Teal | Teal | COOL | winter |
| (기타) | 17색 외 확장 | - | 21색 팔레트 (09-dress-skirt.md) |

### 2.3. 사용 시나리오
```
[사용자] "Drive 이미지에서 색상 추천해줘"
   [시스템] → Drive API 인증
          → 폴더 5명 × 2-3 카테고리 = 12개
          → 각 이미지 색상 추출 (FashionSigLIP)
          → 17색 매핑 (color_classifier)
          → 카테고리별 빈도 계산
          → "Drive 멤버 70%가 Black/Beige/Denim 선호" 같은 인사이트 생성
          → 추천 시 가중치
```

---

## 3. 계절별 선호 색상 (실제 시장 데이터)

### 3.1. 🌸 봄 (3-5월) - Pastel + Color Clash

**데이터 출처**:
- 지그재그 2024 봄: "컬러의 해방" 트렌드, 올리브 545%↑, 민트 380%↑, 보라 162%↑
- 매경 2024 봄: 피치퍼즈 (Pantone), 버터옐로, 라일락
- Vogue 2024 S/S: 베이비 블루, 민트 그린, 노란 기 빠진 아이보리, 연분홍

**계절 베스트 팔레트 (17색 매핑)**:
| 추천 | hex | 카테고리 | 시즌 anchor | 빈도 |
|------|-----|---------|------------|------|
| Peach Fuzz (피치퍼즈) | #FFBE98 | WARM | 봄웜 | ★★★★★ (Pantone 2024) |
| Light Coral | #FF8F7A | WARM | 봄웜 | ★★★★ |
| Butter Yellow | #F5E6A8 | WARM | 봄웜 | ★★★★ |
| Lilac / Lavender | #B57EDC | MUTED/COOL | 여름쿨 | ★★★ |
| Mint | #98E0C0 | MUTED/COOL | 여름쿨 | ★★★★★ (380%↑) |
| Olive (Spring Light) | #C4B582 | WARM | 봄웜 | ★★★★★ (545%↑) |
| Baby Blue | #B0E0E6 | MUTED/COOL | 여름쿨 | ★★★★ |
| Soft Rose | #C894AD | MUTED | 여름쿨 | ★★★ |
| Pure White | #FFFFFF | NEUTRAL | universal | ★★★★ |

**베스트 매치** (봄 웜톤):
- Peach Fuzz + Cream
- Light Coral + Beige
- Butter Yellow + White

### 3.2. ☀️ 여름 (6-8월) - Cool + Light

**데이터 출처**:
- theguide.co.kr 여름 민트 코디: 화이트·베이지·데님이 90% 매치
- km0506: 라이트베이지·라이트카키·소프트블루·버터옐로우
- 다움 (daum): 화이트·스카이블루·민트·네이비 추천

**계절 베스트 팔레트**:
| 추천 | hex | 카테고리 | 시즌 anchor | 빈도 |
|------|-----|---------|------------|------|
| Light Beige | #E8D5B7 | NEUTRAL | universal | ★★★★★ |
| Light Khaki | #C4B582 | NEUTRAL | universal | ★★★★ |
| Soft Blue | #ADD8E6 | COOL | 여름쿨 | ★★★★ |
| Mint | #98E0C0 | MUTED/COOL | 여름쿨 | ★★★★★ |
| White | #FFFFFF | NEUTRAL | universal | ★★★★★ |
| Sky Blue | #87CEEB | COOL | 여름쿨 | ★★★★ |
| Light Coral | #FF8F7A | WARM | 봄웜 | ★★★ |
| Cream | #F2E8D5 | NEUTRAL | universal | ★★★★ |

**베스트 매치** (여름 쿨톤):
- Mint + White
- Soft Blue + Beige
- Light Beige + White
- Mint + Beige (가장 안전)

### 3.3. 🍂 가을 (9-11월) - Earth tone + Burgundy

**데이터 출처**:
- 매경 2024 FW: 모카 무스 (Pantone 2025), 브라운 43% (+127%), 버건디 강세
- LF 2024 FW: 올리브 120%↑, 카키 90%↑, 퍼플 40%↑
- 2025 F/W 7가지 컬러: 모카브라운·버건디·올리브그린·캐멀·머스타드
- VOGUE 2024 FW: 체리 마르살라 (와인), 트렌치 + 체크

**계절 베스트 팔레트**:
| 추천 | hex | 카테고리 | 시즌 anchor | 빈도 |
|------|-----|---------|------------|------|
| Mocha Brown | #6B4F3A | WARM | 가을웜 | ★★★★★ (Pantone 2025) |
| Burgundy | #7A1F4F | WARM | 가을웜 | ★★★★★ |
| Olive Green | #6B6B45 | WARM | 가을웜 | ★★★★★ (120%↑) |
| Khaki | #8B7355 | NEUTRAL/MUTED | universal | ★★★★ |
| Camel | #C19A6B | WARM | 가을웜 | ★★★★ |
| Mustard | #D4A017 | WARM | 가을웜 | ★★★★ |
| Rust | #B5523A | WARM | 가을웜 | ★★★ |
| Brown | #6B4F3A | WARM | 가을웜 | ★★★★★ (127%↑) |
| Purple | #6B4F8B | COOL | 겨울쿨 | ★★★ (40%↑) |
| Forest Green | #2E5E4E | COOL | 겨울쿨 | ★★★ |

**베스트 매치** (가을 웜톤):
- Burgundy + Brown
- Burgundy + Beige
- Olive + Brown
- Camel + Chocolate Brown
- Mustard + Gray

### 3.4. ❄️ 겨울 (12-2월) - Deep + High contrast

**데이터 출처**:
- 매경: 네이비 → 블랙 → 차콜그레이 → 카키 → 베이지 (구매 순서)
- whowhatwear: Choclate Brown (Black is officially out)
- VOGUE 2024 FW: 코트 베이지/카멜/차콜그레이, 패딩 블랙/네이비/머스타드

**계절 베스트 팔레트**:
| 추천 | hex | 카테고리 | 시즌 anchor | 빈도 |
|------|-----|---------|------------|------|
| Black | #1E1E2E | NEUTRAL | universal | ★★★★★ |
| Navy | #1B2444 | NEUTRAL | universal | ★★★★★ |
| Charcoal | #36454F | NEUTRAL | universal | ★★★★★ |
| Chocolate Brown | #4A2C20 | WARM | 가을웜 | ★★★★★ (Whowhatwear 2024) |
| Camel | #C19A6B | WARM | 가을웜 | ★★★★ |
| Burgundy | #7A1F4F | WARM | 가을웜 | ★★★★ |
| Beige | #D9C3A5 | NEUTRAL | universal | ★★★★ |
| Cream | #F2E8D5 | NEUTRAL | universal | ★★★ |
| Mustard | #D4A017 | WARM | 가을웜 | ★★★ (패딩 포인트) |
| Forest Green | #2E5E4E | COOL | 겨울쿨 | ★★★ |
| Olive | #6B6B45 | WARM | 가을웜 | ★★★ |

**베스트 매치** (겨울 쿨톤):
- Black + Cream
- Navy + Camel
- Charcoal + Burgundy
- Black + Burgundy
- Camel + Black (모던)

---

## 4. 4시즌 × 4시점 매트릭스 (실제 시장)

| | 🌸 봄 (3-5월) | ☀️ 여름 (6-8월) | 🍂 가을 (9-11월) | ❄️ 겨울 (12-2월) |
|---|--------------|----------------|------------------|------------------|
| **WARM** 메인 | Peach Fuzz, Light Coral, Butter Yellow | (소량) Light Coral | Burgundy, Olive, Brown, Mustard, Rust | Burgundy, Olive, Camel |
| **COOL** 메인 | (소량) | Soft Blue, Sky Blue, Mint | Purple, Forest Green | Navy, Charcoal, Black |
| **NEUTRAL** | White, Beige, Cream | White, Light Beige, Cream | Beige, Khaki, Brown | Black, Navy, Charcoal, Beige |
| **MUTED** | Lavender, Soft Rose, Mint | Mint, Lavender, Dusty Rose | Mauve, Stone, Sage | (소량) Deep Plum, Forest |

**→ 계절별 추천 시**: 위 매트릭스 + 퍼스널컬러 anchor 결합
- 봄웜 사용자 + 봄 → WARM 카테고리 가중치 ↑ (Peach Fuzz + Cream)
- 겨울쿨 사용자 + 겨울 → COOL/NEUTRAL 가중치 ↑ (Black + Charcoal)
- 여름쿨 사용자 + 여름 → COOL/MUTED 가중치 ↑ (Mint + Beige)
- 가을웜 사용자 + 가을 → WARM 가중치 ↑ (Burgundy + Brown)

---

## 5. 활용 시나리오

### 5.1. 추구미 (PursuitMe)
- **계절 필터** 추가 (봄/여름/가을/겨울)
- 사용자 시즌 + 현재 계절 매칭 → 자동 색상 우선순위
- 예: 봄웜 사용자 + 봄 → "지금 시즌엔 Peach Fuzz + Cream 추천"

### 5.2. 채팅 에이전트
```
사용자: "여름에 입을 화사한 원피스 추천"
에이전트: 
  → 사용자 시즌: 여름쿨
  → 계절: 여름
  → 추천: "Lavender + Mint 원피스 + Beige 액세서리"
  → 이유: "여름쿨 anchor + 여름 시장 베스트 (Mint 90% 매치)"
```

### 5.3. 옷장 RAG
- RAG 결과 + Drive 멤버 색상 분포 → "당신 옷장에 Lavender가 없네요. 추가 추천"
- 4시즌 anchor + RAG 색상 매칭

### 5.4. Drive 이미지 자동 반영
```
[1] Drive API로 폴더 12개 이미지 다운로드
[2] FashionSigLIP으로 dominant color 추출
[3] 17색 centroid로 매핑
[4] 멤버별 색상 분포 계산
[5] "김민욱 70% Black/Beige/Denim → 추천 가중치"
```

---

## 6. 데이터 출처

### 6.1. Drive
- 폴더: 골든셋(좋은 코디) - https://drive.google.com/drive/u/1/folders/178wPfnaVOwRrOyKjOMvTSNE_wtFBCShy
- 5명 × 2-3 카테고리 = 12 폴더, 200+ 이미지
- 직접 접근 시 Google Drive API credentials 필요 (OAuth)

### 6.2. 시장 통계
- 지그재그 2024 봄 컬러의 해방 (매경)
- 매경 2024 FW / 2025 F/W 트렌드
- Vogue 2024 S/S, F/W
- theguide.co.kr 여름 코디
- 다움 2024 여름
- Whowhatwear UK 2024 Winter

### 6.3. Pantone
- 2024: Peach Fuzz
- 2025: Mocha Mousse

---

## 7. 한계

1. **Drive 직접 접근 불가**: Google API 인증 필요, OAuth 토큰 별도 작업
2. **시장 데이터 한정**: 4계절 통계가 일반화된 데이터, 한국 시장 편향
3. **2024-2025 데이터**: 시간 경과 시 업데이트 필요
4. **성별 편향**: Drive가 men/women 분리, unisex는 별도 처리 필요

## 8. 후속 작업

1. **Google Drive API 인증** (OAuth credentials) → 자동 색상 추출 파이프라인
2. **2025 F/W 업데이트** (현재 2024 데이터 위주)
3. **성별/연령별 추가 데이터** (현재 20-30대 중심)
4. **시즌 × 퍼스널컬러 cross-tab** (16 sub-type별 계절 추천)
