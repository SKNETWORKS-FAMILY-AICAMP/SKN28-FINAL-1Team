# - PreferenceOption: 옵션 마스터 (98개 시드)
# - Pursuit: 사용자당 1행, payload = JSONField( nested preferred/avoided )

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

# 98개 옵션 시드 데이터
# - 출처: mobile/src/screens/PursuitPreferenceScreen.tsx MOCK_CATEGORY_OPTIONS
# - 11개 카테고리 × 옵션 개수 = 4 + 16 + 29 + 14 + 4 + 4 + 4 + 7 + 4 + 4 + 6 = 98

OPTIONS_SEED = [
    # ── seasons (4) ──
    ("seasons", 0,  "spring", "봄",  {}),
    ("seasons", 1,  "summer", "여름", {}),
    ("seasons", 2,  "autumn", "가을", {}),
    ("seasons", 3,  "winter", "겨울", {}),
    # ── styles (16) ──
    ("styles", 0,  "minimal",          "미니멀",            {}),
    ("styles", 1,  "casual",           "캐주얼",            {}),
    ("styles", 2,  "street",           "스트릿",            {}),
    ("styles", 3,  "classic",          "클래식",            {}),
    ("styles", 4,  "lovely",           "러블리",            {}),
    ("styles", 5,  "chic",             "시크",              {}),
    ("styles", 6,  "sporty",           "스포티",            {}),
    ("styles", 7,  "vintage",          "빈티지",            {}),
    ("styles", 8,  "romantic",         "로맨틱",            {}),
    ("styles", 9,  "elegance",         "엘레강스",          {}),
    ("styles", 10, "retro",            "레트로",            {}),
    ("styles", 11, "modern",           "모던",              {}),
    ("styles", 12, "business",         "비즈니스",          {}),
    ("styles", 13, "business_casual",  "비즈니스 캐주얼",   {}),
    ("styles", 14, "americasual",      "아메카지",          {}),
    ("styles", 15, "boyish",           "보이시",            {}),
    # ── colors (29) ──
    ("colors", 0,  "black",       "블랙",         {"color_hex": "#000000"}),
    ("colors", 1,  "ivory",       "아이보리",     {"color_hex": "#FFFFF0"}),
    ("colors", 2,  "white",       "화이트",       {"color_hex": "#FFFFFF"}),
    ("colors", 3,  "gray",        "그레이",       {"color_hex": "#808080"}),
    ("colors", 4,  "charcoal",    "차콜",         {"color_hex": "#36454F"}),
    ("colors", 5,  "navy",        "네이비",       {"color_hex": "#000080"}),
    ("colors", 6,  "beige",       "베이지",       {"color_hex": "#F5F5DC"}),
    ("colors", 7,  "brown",       "브라운",       {"color_hex": "#8B4513"}),
    ("colors", 8,  "olive",       "올리브",       {"color_hex": "#556B2F"}),
    ("colors", 9,  "khaki",       "카키",         {"color_hex": "#C3B091"}),
    ("colors", 10, "carmel",      "카멜",         {"color_hex": "#C19A6B"}),
    ("colors", 11, "denim_blue",  "데님블루",     {"color_hex": "#1560BD"}),
    ("colors", 12, "light_pink",  "라이트 핑크",  {"color_hex": "#FFB6C1"}),
    ("colors", 13, "pink",        "핑크",         {"color_hex": "#FFC0CB"}),
    ("colors", 14, "rose",        "로즈",         {"color_hex": "#FF007F"}),
    ("colors", 15, "mauve",       "모브",         {"color_hex": "#B784A7"}),
    ("colors", 16, "peach",       "피치",         {"color_hex": "#FFDAB9"}),
    ("colors", 17, "coral",       "코럴",         {"color_hex": "#FF7F50"}),
    ("colors", 18, "light_blue",  "라이트 블루",  {"color_hex": "#ADD8E6"}),
    ("colors", 19, "blue",        "블루",         {"color_hex": "#0000FF"}),
    ("colors", 20, "mint",        "민트",         {"color_hex": "#3EB489"}),
    ("colors", 21, "green",       "그린",         {"color_hex": "#05C905"}),
    ("colors", 22, "red",         "레드",         {"color_hex": "#FF0000"}),
    ("colors", 23, "burgundy",    "버건디",       {"color_hex": "#800020"}),
    ("colors", 24, "yellow",      "옐로우",       {"color_hex": "#FFDB58"}),
    ("colors", 25, "purple",      "퍼플",         {"color_hex": "#800080"}),
    ("colors", 26, "orange",      "오렌지",       {"color_hex": "#FFA500"}),
    ("colors", 27, "silver",      "실버",         {"color_hex": "#C0C0C0"}),
    ("colors", 28, "gold",        "골드",         {"color_hex": "#FFD700"}),
    # ── necklines (14) ──
    ("necklines", 0,  "round",         "라운드넥",  {"icon": "round-neck"}),
    ("necklines", 1,  "vneck",         "브이넥",    {"icon": "v-neck"}),
    ("necklines", 2,  "uneck",         "유넥",      {"icon": "u-neck"}),
    ("necklines", 3,  "hood",          "후드",      {"icon": "hood"}),
    ("necklines", 4,  "square",        "스퀘어넥",  {"icon": "square-neck"}),
    ("necklines", 5,  "off_shoulder",  "오프숄더",  {"icon": "off-shoulder"}),
    ("necklines", 6,  "half_high",     "반하이넥",  {"icon": "half-high"}),
    ("necklines", 7,  "one_shoulder",  "원숄더",    {"icon": "one-shoulder"}),
    ("necklines", 8,  "halter",        "홀터넥",    {"icon": "halter-neck"}),
    ("necklines", 9,  "boat",          "보트넥",    {"icon": "boat-neck"}),
    ("necklines", 10, "heart",         "하트넥",    {"icon": "sweetheart-neck"}),
    ("necklines", 11, "turtle",        "터틀넥",    {"icon": "turtleneck"}),
    ("necklines", 12, "high",          "하이넥",    {"icon": "high-neck"}),
    ("necklines", 13, "half_zip",      "반집업",    {"icon": "half-zip"}),
    # ── top_fits (4) ──
    ("top_fits", 0, "normal",    "노멀핏", {"icon": "normal-fit"}),
    ("top_fits", 1, "slim",      "슬림핏", {"icon": "slim-fit"}),
    ("top_fits", 2, "loose",     "루즈핏", {"icon": "loose-fit"}),
    ("top_fits", 3, "oversized", "오버핏", {"icon": "over-fit"}),
    # ── top_lengths (4) ──
    ("top_lengths", 0, "crop",    "크롭",    {"icon": "crop"}),
    ("top_lengths", 1, "short",   "숏",      {"icon": "short-length"}),
    ("top_lengths", 2, "regular", "레귤러",  {"icon": "regular-length"}),
    ("top_lengths", 3, "long",    "롱",      {"icon": "long-length"}),
    # ── sleeves (4) ──
    ("sleeves", 0, "long",         "긴소매",   {"icon": "long-sleeve"}),
    ("sleeves", 1, "short",        "반소매",   {"icon": "short-sleeve"}),
    ("sleeves", 2, "three_quarter", "7부소매",  {"icon": "three-quarter-sleeve"}),
    ("sleeves", 3, "sleeveless",   "민소매",   {"icon": "sleeveless"}),
    # ── pants_fits (7) ──
    ("pants_fits", 0, "wide",       "와이드",     {"icon": "wide"}),
    ("pants_fits", 1, "jogger",     "조거",       {"icon": "jogger"}),
    ("pants_fits", 2, "straight",   "스트레이트", {"icon": "straight"}),
    ("pants_fits", 3, "skinny",     "스키니",     {"icon": "skinny"}),
    ("pants_fits", 4, "bootcut",    "부츠컷",     {"icon": "bootcut"}),
    ("pants_fits", 5, "slacks",     "슬랙스",     {"icon": "slacks"}),
    ("pants_fits", 6, "semi_wide",  "세미와이드", {"icon": "semi-wide"}),
    # ── pants_lengths (4) ──
    ("pants_lengths", 0, "short_shorts", "짧은 반바지(3부)", {"icon": "short-shorts-3"}),
    ("pants_lengths", 1, "shorts",       "반바지(5부)",      {"icon": "shorts-5"}),
    ("pants_lengths", 2, "seven_part",   "7부",             {"icon": "three-quarter-pants"}),
    ("pants_lengths", 3, "long_pants",   "긴바지",          {"icon": "long-pants"}),
    # ── skirt_lengths (4) ──
    ("skirt_lengths", 0, "mini", "미니", {"icon": "mini"}),
    ("skirt_lengths", 1, "midi", "미디", {"icon": "midi"}),
    ("skirt_lengths", 2, "long", "롱",  {"icon": "long-skirt"}),
    ("skirt_lengths", 3, "maxi", "맥시", {"icon": "maxi"}),
    # ── skirt_types (6) ──
    ("skirt_types", 0, "aline",   "A라인",      {"icon": "a-line"}),
    ("skirt_types", 1, "pleats",  "플리츠",     {"icon": "pleated"}),
    ("skirt_types", 2, "flare",   "플레어 라인", {"icon": "flare"}),
    ("skirt_types", 3, "hline",   "H라인",     {"icon": "h-line"}),
    ("skirt_types", 4, "mermaid", "머메이드",   {"icon": "mermaid"}),
    ("skirt_types", 5, "balloon", "벌룬",      {"icon": "balloon"}),
]


def seed_options(apps, schema_editor):
    PreferenceOption = apps.get_model("users", "PreferenceOption")
    for category, order, code, label, meta in OPTIONS_SEED:
        PreferenceOption.objects.update_or_create(
            category=category,
            code=code,
            defaults={"label": label, "order": order, "meta": meta},
        )


def unseed_options(apps, schema_editor):
    PreferenceOption = apps.get_model("users", "PreferenceOption")
    PreferenceOption.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_bodyphototransaction'),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS pursuits CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name='PreferenceOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[
                    ('seasons', '계절'),
                    ('styles', '스타일'),
                    ('colors', '색상'),
                    ('necklines', '넥라인'),
                    ('top_fits', '상의핏'),
                    ('top_lengths', '상의기장'),
                    ('sleeves', '소매길이'),
                    ('pants_fits', '팬츠핏'),
                    ('pants_lengths', '팬츠기장'),
                    ('skirt_lengths', '스커트기장'),
                    ('skirt_types', '스커트타입'),
                ], max_length=50, verbose_name='카테고리')),
                ('code', models.CharField(max_length=50, verbose_name='옵션 코드')),
                ('label', models.CharField(max_length=50, verbose_name='라벨')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='정렬 순서')),
                ('meta', models.JSONField(blank=True, default=dict, verbose_name='메타데이터')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성 시각')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정 시각')),
            ],
            options={
                'verbose_name': '선호도 옵션',
                'verbose_name_plural': '선호도 옵션',
                'db_table': 'preference_options',
                'ordering': ['category', 'order', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='preferenceoption',
            constraint=models.UniqueConstraint(
                fields=('category', 'code'),
                name='uq_preference_option_category_code',
            ),
        ),
        migrations.CreateModel(
            name='Pursuit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payload', models.JSONField(blank=True, default=dict, verbose_name='선호/기피 데이터')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성 시각')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정 시각')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='pursuit', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': '추구미',
                'verbose_name_plural': '추구미',
                'db_table': 'pursuits',
            },
        ),
        # 98개 옵션 시드
        migrations.RunPython(seed_options, unseed_options),
    ]
