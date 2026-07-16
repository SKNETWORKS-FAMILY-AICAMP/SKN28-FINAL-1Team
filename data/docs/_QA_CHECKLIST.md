# QA Checklist for Rule JSONs and README

## JSON Validation
- [ ] All JSON files parse without error
- [ ] No null values in required fields
- [ ] All arrays properly formatted

## Schema Consistency
- [ ] id field uses snake_case
- [ ] description field is present in all objects
- [ ] keywords field is array of Korean strings
- [ ] avoid field is array of Korean strings

## Korean Language Baseline
- [ ] Color names: use Korean (블랙, 화이트, 그레이, 베이지, 네이비, 카멜, 버건디, 핑크, 민트, 라벤더)
- [ ] Style names: use Korean (미니멀, 스트릿, 캐주얼, 시크, 페미닌, 빈티지, 스포티, 프레피)
- [ ] Weather terms: use Korean (비, 눈, 강풍, 맑음, 흐림)
- [ ] No English color names like "black", "white", "navy"

## README Compliance
- [ ] Has §1 요약
- [ ] Has §2 데이터 구조 상세 (with S3 evidence)
- [ ] Has §3 추천 시스템 활용 방안
- [ ] Has §4 출처 (S3 path, Confluence)
