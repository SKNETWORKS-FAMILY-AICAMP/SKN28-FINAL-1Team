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

    def test_chat_apis_share_one_executable_swagger_category(self) -> None:
        response = self.client.get(
            reverse("api-schema"),
            headers={"accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)
        paths = schema["paths"]

        chat_paths = {
            path
            for path in paths
            if path.startswith(("/api/v1/chat/", "/api/v1/recommendations/"))
        }
        self.assertTrue(chat_paths)
        for path in chat_paths:
            for method, operation in paths[path].items():
                if method not in {"get", "post", "patch", "put", "delete"}:
                    continue
                with self.subTest(path=path, method=method):
                    self.assertEqual(operation["tags"], ["채팅"])
                    self.assertTrue(operation.get("summary"))
                    self.assertTrue(operation.get("description"))

        declared_tags = {tag["name"]: tag for tag in schema["tags"]}
        self.assertIn("채팅", declared_tags)
        self.assertIn("추천 카드", declared_tags["채팅"]["description"])

        session_create = paths["/api/v1/chat/sessions/"]["post"]
        session_json = session_create["requestBody"]["content"]["application/json"]
        self.assertEqual(
            set(session_json["examples"]),
            {
                "옷장아이템만사용하는추천대화",
                "새상품을포함하는추천대화",
            },
        )

        message_create = paths[
            "/api/v1/chat/sessions/{session_id}/messages/"
        ]["post"]
        self.assertEqual(
            set(message_create["requestBody"]["content"]),
            {"application/json"},
        )
        message_json = message_create["requestBody"]["content"]["application/json"]
        self.assertIn("첫질문전송", message_json["examples"])
        self.assertIn("OpenAI", message_create["description"])

        attachment_create = paths[
            "/api/v1/chat/sessions/{session_id}/attachments/"
        ]["post"]
        attachment_form = attachment_create["requestBody"]["content"][
            "multipart/form-data"
        ]
        self.assertEqual(
            set(attachment_create["requestBody"]["content"]),
            {"multipart/form-data"},
        )
        self.assertIn("채팅사진과설명업로드", attachment_form["examples"])

        feedback = paths[
            "/api/v1/recommendations/{result_id}/cards/{card_id}/feedback/"
        ]["put"]
        self.assertEqual(
            set(feedback["requestBody"]["content"]),
            {"application/json"},
        )
        feedback_json = feedback["requestBody"]["content"]["application/json"]
        self.assertEqual(
            set(feedback_json["examples"]),
            {"추천이마음에듦", "추천이마음에들지않음"},
        )

        chat_sse = paths["/api/v1/chat/runs/{run_id}/events/"]["get"]
        self.assertIn("text/event-stream", chat_sse["responses"]["200"]["content"])

    def test_chat_swagger_exposes_executable_parameters(self) -> None:
        """채팅 문서가 설명만 있고 입력칸이 사라지는 회귀를 막는다."""

        response = self.client.get(
            reverse("api-schema"),
            headers={"accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)
        paths = schema["paths"]

        expected_parameters = {
            ("get", "/api/v1/chat/sessions/search/"): {
                "query": ("query", True),
                "limit": ("query", False),
                "cursor": ("query", False),
            },
            ("get", "/api/v1/chat/sessions/{session_id}/messages/page/"): {
                "session_id": ("path", True),
                "limit": ("query", False),
                "cursor": ("query", False),
            },
            ("get", "/api/v1/recommendations/"): {
                "mode": ("query", False),
                "limit": ("query", False),
                "offset": ("query", False),
            },
            ("get", "/api/v1/chat/runs/{run_id}/events/"): {
                "run_id": ("path", True),
                "last_event_id": ("query", False),
            },
            (
                "post",
                "/api/v1/chat/sessions/{session_id}/attachments/{attachment_id}/analysis/",
            ): {
                "session_id": ("path", True),
                "attachment_id": ("path", True),
            },
        }
        for (method, path), expected in expected_parameters.items():
            actual = {
                parameter["name"]: (
                    parameter["in"],
                    parameter.get("required", False),
                )
                for parameter in paths[path][method]["parameters"]
            }
            with self.subTest(method=method, path=path):
                self.assertEqual(actual, expected)
                for parameter in paths[path][method]["parameters"]:
                    self.assertTrue(parameter.get("description"))
                    if parameter["name"] != "cursor":
                        self.assertTrue(parameter.get("examples"))

        for path in (
            "/api/v1/chat/sessions/search/",
            "/api/v1/chat/sessions/{session_id}/messages/page/",
        ):
            cursor = next(
                parameter
                for parameter in paths[path]["get"]["parameters"]
                if parameter["name"] == "cursor"
            )
            self.assertNotIn("example", cursor)
            self.assertNotIn("examples", cursor)
            self.assertNotIn("default", cursor.get("schema", {}))

        for path, path_item in paths.items():
            if not path.startswith(
                ("/api/v1/chat/", "/api/v1/recommendations/")
            ):
                continue
            template_names = {
                part[1:-1]
                for part in path.split("/")
                if part.startswith("{") and part.endswith("}")
            }
            for method, operation in path_item.items():
                if method not in {"get", "post", "patch", "put", "delete"}:
                    continue
                declared_path_names = {
                    parameter["name"]
                    for parameter in operation.get("parameters", [])
                    if parameter["in"] == "path"
                }
                with self.subTest(method=method, path=path):
                    self.assertEqual(declared_path_names, template_names)

        components = schema["components"]["schemas"]
        required_request_fields = {
            "ChatSessionCreateRequest": {"mode"},
            "ChatMessageCreateRequest": {"content", "client_message_id"},
            "ChatAttachmentUploadRequest": {"image", "client_message_id"},
            "ChatMoodDecisionRequest": {"decision"},
            "RecommendationFeedbackRequestRequest": {"reaction"},
        }
        for component_name, required_fields in required_request_fields.items():
            component = components[component_name]
            with self.subTest(component=component_name):
                self.assertTrue(required_fields.issubset(set(component["required"])))
                for field_name in component["properties"]:
                    self.assertTrue(
                        component["properties"][field_name].get("description"),
                        f"{component_name}.{field_name} 설명 누락",
                    )

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

    def test_budget_schema_documents_request_body(self) -> None:
        """예산 API는 평범한 APIView라 serializer 추론이 안 된다.

        BudgetViewExtension이 빠지면 PUT request body가 통째로 사라진다.
        """
        response = self.client.get(
            reverse("api-schema"),
            headers={"accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)

        budget = schema["paths"]["/api/v1/users/me/budget/"]
        self.assertEqual(set(budget), {"get", "put"})

        # PUT이 보낼 몸을 실제로 가리키는가 (이게 비면 Swagger에서 입력칸이 안 뜬다)
        request_body = budget["put"]["requestBody"]["content"]["application/json"]
        self.assertEqual(
            request_body["schema"], {"$ref": "#/components/schemas/BudgetRequest"}
        )

        field = schema["components"]["schemas"]["BudgetRequest"]
        self.assertEqual(field["required"], ["monthly_budget"])
        budget_field = field["properties"]["monthly_budget"]
        self.assertTrue(budget_field["nullable"])  # null로 예산 해제
        self.assertEqual(budget_field["minimum"], 10_000)
        self.assertEqual(budget_field["maximum"], 2_147_480_000)
        self.assertIn("1만원 단위", budget_field["description"])

        # 예시 드롭다운 (이름은 drf-spectacular가 공백을 지워 생성한다)
        self.assertEqual(
            set(request_body["examples"]),
            {"예산설정(월30만원)", "예산해제(null)"},
        )
        self.assertIsNone(
            request_body["examples"]["예산해제(null)"]["value"]["monthly_budget"]
        )

        # 응답쪽도 설정됨/미설정 두 가지를 보여준다
        for method in ("get", "put"):
            with self.subTest(method=method):
                ok = budget[method]["responses"]["200"]["content"]["application/json"]
                self.assertEqual(set(ok["examples"]), {"설정됨", "미설정"})

        self.assertEqual(set(budget["put"]["responses"]), {"200", "400", "401"})
        self.assertEqual(set(budget["get"]["responses"]), {"200", "401"})
        self.assertEqual(budget["put"]["operationId"], "update_budget")
        self.assertEqual(budget["get"]["operationId"], "get_budget")

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

    def test_lookbook_schema_is_executable_with_examples(self) -> None:
        response = self.client.get(
            reverse("api-schema"),
            headers={"accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        schema = json.loads(response.content)
        paths = schema["paths"]

        photo = paths["/api/v1/lookbooks/photo/"]["post"]
        photo_multipart = photo["requestBody"]["content"]["multipart/form-data"]
        self.assertIn("룩사진업로드", photo_multipart["examples"])
        # 겹치는 부위를 건너뛴다는 계약이 문서에 남아 있어야 프론트가 왜
        # 상의가 안 뽑혔는지 되묻지 않는다.
        self.assertIn("exclude_categories", photo["description"])
        self.assertEqual(set(photo["responses"]), {"202", "400", "401", "409", "503"})

        wardrobe = paths["/api/v1/lookbooks/wardrobe/"]["post"]
        wardrobe_json = wardrobe["requestBody"]["content"]["application/json"]
        self.assertIn("옷장아이템만골라올리기", wardrobe_json["examples"])

        listing = paths["/api/v1/lookbooks/"]["get"]
        parameters = {parameter["name"]: parameter for parameter in listing["parameters"]}
        self.assertEqual(set(parameters), {"hashtag", "status", "limit", "offset"})
        self.assertEqual(
            listing["responses"]["200"]["content"]["application/json"]["schema"],
            {"$ref": "#/components/schemas/LookbookListResponse"},
        )
        self.assertEqual(
            set(schema["components"]["schemas"]["LookbookListResponse"]["properties"]),
            {"count", "next_offset", "results"},
        )

        detail_path = "/api/v1/lookbooks/{lookbook_id}/"
        self.assertEqual(set(paths[detail_path]), {"get", "patch", "delete"})
        patch_json = paths[detail_path]["patch"]["requestBody"]["content"][
            "application/json"
        ]
        self.assertEqual(
            set(patch_json["examples"]),
            {"전체메타데이터수정", "해시태그만부분수정"},
        )

        status_path = "/api/v1/lookbooks/{lookbook_id}/processing-status/"
        self.assertIn(status_path, paths)

        lookbook_paths = {
            "/api/v1/lookbooks/photo/",
            "/api/v1/lookbooks/wardrobe/",
            "/api/v1/lookbooks/",
            detail_path,
            status_path,
        }
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method not in {"get", "post", "patch", "delete", "put"}:
                    continue
                with self.subTest(path=path, method=method):
                    if path in lookbook_paths:
                        self.assertEqual(operation["tags"], ["룩북"])
                    else:
                        self.assertNotIn("룩북", operation.get("tags", []))
