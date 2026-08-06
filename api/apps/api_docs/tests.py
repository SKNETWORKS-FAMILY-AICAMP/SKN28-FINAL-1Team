import json

from django.test import SimpleTestCase
from django.urls import reverse


class SwaggerEndpointTests(SimpleTestCase):
    def test_schema_contains_current_api_paths(self) -> None:
        response = self.client.get(
            reverse("api-schema"),
            headers={"accept": "application/json"},
        )

        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)
        self.assertIn("/api/v1/auth/{provider}/login/", schema["paths"])
        self.assertIn("/api/v1/auth/token/refresh/", schema["paths"])
        self.assertIn("/api/v1/users/me/", schema["paths"])
        self.assertIn("/api/v1/outfits/analyze/", schema["paths"])

        operation = schema["paths"]["/api/v1/outfits/analyze/"]["post"]
        self.assertIn(
            "multipart/form-data",
            operation["requestBody"]["content"],
        )

    def test_swagger_ui_is_available(self) -> None:
        response = self.client.get(reverse("swagger-ui"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("api-schema"))

    def test_outfit_analysis_detail_documents_wardrobe(self) -> None:
        """조회 응답은 인증 여부로 모양이 갈린다 — 둘 다 문서에 남아 있어야 한다.

        Public만 선언하면 소유자 전용 필드(wardrobe 등)가 Swagger에 아예 안 나온다.
        """
        response = self.client.get(
            reverse("api-schema"),
            headers={"accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)

        detail = schema["paths"]["/api/v1/outfits/analyses/{analysis_id}/"]["get"]
        content = detail["responses"]["200"]["content"]["application/json"]
        components = schema["components"]["schemas"]

        # 비로그인·본인 응답이 oneOf로 둘 다 연결돼 있는가
        self.assertEqual(
            content["schema"], {"$ref": "#/components/schemas/OutfitAnalysisResult"}
        )
        self.assertEqual(
            {ref["$ref"] for ref in components["OutfitAnalysisResult"]["oneOf"]},
            {
                "#/components/schemas/OutfitAnalysisPublic",
                "#/components/schemas/OutfitAnalysisDetail",
            },
        )

        # 옷장 연계 필드와 아이템 요약 스키마
        self.assertIn("wardrobe", components["OutfitAnalysisDetail"]["properties"])
        self.assertEqual(
            set(components["WardrobeLinkedItem"]["properties"]),
            {
                "id",
                "item_name",
                "category_large",
                "category_small",
                "color",
                "image_url",
                "confirmed",
            },
        )

        # 예시 드롭다운 (이름은 drf-spectacular가 공백을 지워 생성한다)
        self.assertEqual(
            set(content["examples"]),
            {
                "본인조회·옷장등록까지완료(DONE)",
                "본인조회·평가는끝났지만옷장은진행중",
                "본인조회·옷장미연계",
                "비로그인조회(축소응답)",
            },
        )
        done = content["examples"]["본인조회·옷장등록까지완료(DONE)"]["value"]
        self.assertEqual(done["wardrobe"]["status"], "DONE")
        self.assertTrue(done["wardrobe"]["items"])

        pending = content["examples"]["본인조회·평가는끝났지만옷장은진행중"]["value"]
        self.assertEqual(pending["wardrobe"]["items"], [])

    def test_calendar_schema_is_executable_with_examples(self) -> None:
        response = self.client.get(
            reverse("api-schema"),
            headers={"accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)
        paths = schema["paths"]

        photo = paths["/api/v1/calendars/photo/"]["post"]
        photo_multipart = photo["requestBody"]["content"]["multipart/form-data"]
        self.assertIn("사진업로드캘린더", photo_multipart["examples"])

        wardrobe = paths["/api/v1/calendars/wardrobe/"]["post"]
        wardrobe_json = wardrobe["requestBody"]["content"]["application/json"]
        self.assertIn("기존옷장아이템직접선택", wardrobe_json["examples"])

        period = paths["/api/v1/calendars/"]["get"]
        parameters = {parameter["name"]: parameter for parameter in period["parameters"]}
        self.assertEqual(set(parameters), {"start_date", "end_date"})
        self.assertTrue(parameters["start_date"]["required"])
        self.assertTrue(parameters["end_date"]["required"])
        self.assertTrue(parameters["start_date"]["examples"])
        self.assertTrue(parameters["end_date"]["examples"])

        detail_path = "/api/v1/calendars/{calendar_id}/"
        self.assertEqual(set(paths[detail_path]), {"get", "patch", "delete"})
        patch_json = paths[detail_path]["patch"]["requestBody"]["content"][
            "application/json"
        ]
        self.assertEqual(
            set(patch_json["examples"]),
            {"전체메타데이터수정", "일정만부분수정"},
        )

        status_path = "/api/v1/calendars/{calendar_id}/processing-status/"
        self.assertIn(status_path, paths)

        calendar_paths = {
            "/api/v1/calendars/photo/",
            "/api/v1/calendars/wardrobe/",
            "/api/v1/calendars/",
            "/api/v1/calendars/by-date/",
            detail_path,
            status_path,
        }
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method not in {"get", "post", "patch", "delete", "put"}:
                    continue
                with self.subTest(path=path, method=method):
                    if path in calendar_paths:
                        self.assertEqual(operation["tags"], ["캘린더"])
                    else:
                        self.assertNotIn("캘린더", operation.get("tags", []))
