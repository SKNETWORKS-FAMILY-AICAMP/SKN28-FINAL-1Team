# Weather Collector 사용 메모

## 핵심 구조

- `weather_area`: 전국 수집 대상 격자/중기 예보구역 마스터
- `weather_nowcast_raw`: 실황
- `weather_very_short_raw`: 초단기예보
- `weather_short_raw`: 단기예보
- `weather_mid_land_raw`: 중기 육상예보
- `weather_mid_temp_raw`: 중기 기온예보

## 실행 예시

```bash
python weather_collector_db.py --init-schema
python weather_collector_db.py --sync-areas
python weather_collector_db.py --job nowcast
python weather_collector_db.py --job very_short
python weather_collector_db.py --job short
python weather_collector_db.py --scheduler
```

## Docker 실행 예시

```bash
cp .env.weather.example .env
# .env의 KMA_AUTH_KEY와 URL 수정
mkdir -p data
# data/동네예보지점좌표(위경도)_202601.xlsx 배치
# 중기 수집 시 data/mid_land_areas.json, data/mid_temp_areas.json 배치

docker compose -f docker-compose.weather.yml up --build
```

## 수집 스케줄

- 실황: 매시 10분
- 초단기예보: 매시 45분
- 단기예보: 02:15, 05:15, 08:15, 11:15, 14:15, 17:15, 20:15, 23:15
- 중기 육상/기온: 06:15, 18:15

## 주의

- `--init-schema`는 로컬 테스트용이다. Django 프로젝트에 붙일 때는 Django model/migration으로 스키마를 만들고, collector에서는 `--sync-areas`, `--scheduler`만 실행하는 방식이 낫다.
- `updated_at`은 DB row 수정 시각이다. 예보 최신성 판단은 `base_datetime` 기준으로 해야 한다.
- `raw_data`는 API 전체 응답이 아니라 해당 row 생성에 사용된 원본 item/필드 묶음으로 저장한다.
- 중기 API URL은 계정에서 신청한 URL을 `MID_LAND_URL`, `MID_TEMP_URL`에 넣어야 한다.
