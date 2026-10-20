import base64
import json
from urllib.parse import parse_qs, unquote

import httpx
import pytest

from greenplan import visual

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
JPEG = b"\xff\xd8\xff" + b"1" * 32
SUMMARY = {"trees": 797, "shrubs": 6615, "area_m2": 87897.2}
OBJECTS = ["ROAD", "PAVEMENT", "LIGHTING", "PIPE_GAS"]
ENV = ("GREENPLAN_AI_PROVIDER", "GREENPLAN_AI_TIMEOUT", "FUSIONBRAIN_KEY", "FUSIONBRAIN_SECRET", "FUSIONBRAIN_URL",
       "YANDEX_API_KEY", "YANDEX_FOLDER_ID", "YANDEX_OAUTH_TOKEN", "YANDEX_IAM_TOKEN", "YANDEX_URL",
       "GIGACHAT_AUTH_KEY", "GIGACHAT_CREDENTIALS", "GIGACHAT_SCOPE", "GIGACHAT_URL", "GIGACHAT_AUTH_URL",
       "GIGACHAT_MODEL", "GIGACHAT_CA_BUNDLE", "GIGACHAT_VERIFY_SSL", "POLLINATIONS_KEY", "POLLINATIONS_URL",
       "POLLINATIONS_MODEL")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("POLLINATIONS", "0")
    visual._tokens.clear()


def no_sleep(_):
    return None


def mock(handler):
    return httpx.MockTransport(handler)


def test_prompt_describes_plan():
    prompt = visual.build_prompt(SUMMARY, "layer", OBJECTS, "autumn")
    assert "797" in prompt and "6615" in prompt
    assert "8,8 га" in prompt
    assert "проезжая часть" in prompt
    assert "осенний" in prompt
    assert "газопровод" not in prompt.lower()
    assert len(prompt) <= 1000


def test_street_prompt():
    assert "улицы" in visual.build_prompt(SUMMARY, "corridor", [], "summer")


def test_english_prompt_for_flux():
    prompt = visual.build_prompt({**SUMMARY, "hedges_m": 120, "flowerbeds": 4}, "layer", OBJECTS, "winter", "en")
    assert "8.8 ha" in prompt
    assert "hedges" in prompt and "flower beds" in prompt
    assert "snow" in prompt
    assert not any("а" <= char <= "я" for char in prompt.lower())


def test_everything_off_is_unavailable():
    assert visual.status()["available"] is False
    with pytest.raises(visual.VisualizationUnavailable):
        visual.generate(SUMMARY, "layer", OBJECTS)


def test_no_keys_falls_back_to_pollinations(monkeypatch):
    monkeypatch.delenv("POLLINATIONS")
    state = visual.status()
    assert state["available"] is True
    assert state["providers"] == ["pollinations"]
    assert "Pollinations" in state["message"]


def test_kandinsky_pipeline_api(monkeypatch):
    monkeypatch.setenv("FUSIONBRAIN_KEY", "k")
    monkeypatch.setenv("FUSIONBRAIN_SECRET", "s")
    seen = {"polls": 0}

    def handler(request: httpx.Request):
        assert request.headers["X-Key"] == "Key k"
        assert request.headers["X-Secret"] == "Secret s"
        path = request.url.path
        if path.endswith("/pipelines"):
            return httpx.Response(200, json=[{"id": "pipe-1", "name": "Kandinsky"}])
        if path.endswith("/pipeline/run"):
            body = request.content.decode("utf-8", "ignore")
            assert "pipe-1" in body and "generateParams" in body
            return httpx.Response(201, json={"uuid": "u-1", "status": "INITIAL"})
        if path.endswith("/pipeline/status/u-1"):
            seen["polls"] += 1
            if seen["polls"] < 2:
                return httpx.Response(200, json={"uuid": "u-1", "status": "PROCESSING"})
            return httpx.Response(200, json={"uuid": "u-1", "status": "DONE",
                                             "result": {"files": [base64.b64encode(PNG).decode()], "censored": False}})
        return httpx.Response(404)

    picture = visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(handler), sleep=no_sleep)
    assert picture.provider == "kandinsky"
    assert picture.image == PNG
    assert picture.data_url().startswith("data:image/png;base64,")
    assert picture.extension == "png"
    assert seen["polls"] == 2


def test_kandinsky_legacy_models_api(monkeypatch):
    monkeypatch.setenv("FUSIONBRAIN_KEY", "k")
    monkeypatch.setenv("FUSIONBRAIN_SECRET", "s")

    def handler(request: httpx.Request):
        path = request.url.path
        if path.endswith("/pipelines"):
            return httpx.Response(404)
        if path.endswith("/models"):
            return httpx.Response(200, json=[{"id": 4, "type": "TEXT2IMAGE"}])
        if path.endswith("/text2image/run"):
            return httpx.Response(201, json={"uuid": "u-2", "status": "INITIAL"})
        if path.endswith("/text2image/status/u-2"):
            return httpx.Response(200, json={"status": "DONE", "images": [base64.b64encode(PNG).decode()]})
        return httpx.Response(404)

    picture = visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(handler), sleep=no_sleep)
    assert picture.image == PNG


def test_kandinsky_failure_is_reported(monkeypatch):
    monkeypatch.setenv("FUSIONBRAIN_KEY", "k")
    monkeypatch.setenv("FUSIONBRAIN_SECRET", "s")

    def handler(request: httpx.Request):
        path = request.url.path
        if path.endswith("/pipelines"):
            return httpx.Response(200, json=[{"id": "pipe-1"}])
        if path.endswith("/pipeline/run"):
            return httpx.Response(201, json={"uuid": "u-3"})
        return httpx.Response(200, json={"status": "FAIL", "errorDescription": "очередь переполнена"})

    with pytest.raises(visual.VisualizationFailed, match="Kandinsky.*очередь"):
        visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(handler), sleep=no_sleep)


def yandex_handler(seen):
    def handler(request: httpx.Request):
        seen.setdefault("auth", request.headers.get("Authorization"))
        if request.url.path.endswith("/imageGenerationAsync"):
            assert request.headers["x-folder-id"] == "folder"
            body = json.loads(request.content)
            assert body["modelUri"] == "art://folder/yandex-art/latest"
            assert body["messages"][0]["text"]
            return httpx.Response(200, json={"id": "op-1", "done": False})
        if request.url.path.endswith("/operations/op-1"):
            return httpx.Response(200, json={"id": "op-1", "done": True,
                                             "response": {"image": base64.b64encode(JPEG).decode()}})
        if request.url.host == "iam.api.cloud.yandex.net":
            assert json.loads(request.content) == {"yandexPassportOauthToken": "y0_token"}
            seen["exchanged"] = True
            return httpx.Response(200, json={"iamToken": "t1.iam"})
        return httpx.Response(404)
    return handler


def test_yandexart(monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", " AQVNkey\n")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "folder")
    seen = {}
    picture = visual.generate(SUMMARY, "corridor", OBJECTS, transport=mock(yandex_handler(seen)), sleep=no_sleep)
    assert picture.provider == "yandexart"
    assert picture.mime == "image/jpeg"
    assert seen["auth"] == "Api-Key AQVNkey"


def test_yandex_oauth_token_is_exchanged(monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "y0_token")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "folder")
    seen = {}

    def handler(request: httpx.Request):
        response = yandex_handler(seen)(request)
        if request.url.host != "iam.api.cloud.yandex.net":
            assert request.headers["Authorization"] == "Bearer t1.iam"
        return response

    picture = visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(handler), sleep=no_sleep)
    assert picture.image == JPEG
    assert seen["exchanged"]


def test_yandex_key_id_instead_of_secret(monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "ajeabcdefghijklmnopq")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "folder")
    with pytest.raises(visual.VisualizationFailed, match="AQVN"):
        visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(lambda r: httpx.Response(500)), sleep=no_sleep)


def test_yandex_forbidden_names_the_role(monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "AQVNkey")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "folder")

    def handler(request):
        return httpx.Response(403, json={"error": {"grpcCode": 7, "message": "Permission denied"}})

    with pytest.raises(visual.VisualizationFailed, match="ai.imageGeneration.user") as caught:
        visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(handler), sleep=no_sleep)
    assert "Permission denied" in str(caught.value)


def gigachat_handler(seen, content='Готово. <img src="file-42" fuse="true"/>'):
    def handler(request: httpx.Request):
        if request.url.host == "ngw.devices.sberbank.ru":
            seen["oauth"] = seen.get("oauth", 0) + 1
            assert request.headers["Authorization"] == "Basic YWJjOmRlZg=="
            assert len(request.headers["RqUID"]) == 36
            assert parse_qs(request.content.decode()) == {"scope": ["GIGACHAT_API_PERS"]}
            return httpx.Response(200, json={"access_token": "tok", "expires_at": 4_102_444_800_000})
        assert request.headers["Authorization"] == "Bearer tok"
        if request.url.path.endswith("/chat/completions"):
            body = json.loads(request.content)
            assert body["function_call"] == "auto"
            assert body["messages"][-1]["content"].startswith("Нарисуй")
            seen["host"] = request.url.host
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})
        if request.url.path.endswith("/files/file-42/content"):
            assert request.headers["Accept"] == "application/jpg"
            return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})
        return httpx.Response(404)
    return handler


def test_gigachat(monkeypatch):
    monkeypatch.setenv("GIGACHAT_AUTH_KEY", "Basic YWJjOmRlZg==")
    seen = {}
    picture = visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(gigachat_handler(seen)), sleep=no_sleep)
    assert picture.provider == "gigachat"
    assert picture.image == JPEG
    assert picture.meta["file_id"] == "file-42"
    assert seen["host"] == "api.giga.chat"
    visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(gigachat_handler(seen)), sleep=no_sleep)
    assert seen["oauth"] == 1


def test_gigachat_falls_back_to_old_host(monkeypatch):
    monkeypatch.setenv("GIGACHAT_AUTH_KEY", "YWJjOmRlZg==")
    seen = {}
    inner = gigachat_handler(seen)

    def handler(request):
        if request.url.host == "api.giga.chat":
            raise httpx.ConnectError("Name or service not known", request=request)
        return inner(request)

    picture = visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(handler), sleep=no_sleep)
    assert picture.image == JPEG
    assert seen["host"] == "gigachat.devices.sberbank.ru"


def test_gigachat_text_reply(monkeypatch):
    monkeypatch.setenv("GIGACHAT_AUTH_KEY", "YWJjOmRlZg==")
    handler = gigachat_handler({}, content="Не могу нарисовать это изображение.")
    with pytest.raises(visual.VisualizationFailed, match="текстом"):
        visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(handler), sleep=no_sleep)


def test_gigachat_certificate_hint(monkeypatch):
    monkeypatch.setenv("GIGACHAT_AUTH_KEY", "YWJjOmRlZg==")

    def handler(request):
        raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] self-signed certificate in chain", request=request)

    with pytest.raises(visual.VisualizationFailed, match="GIGACHAT_CA_BUNDLE"):
        visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(handler), sleep=no_sleep)


def test_gigachat_bad_key(monkeypatch):
    monkeypatch.setenv("GIGACHAT_AUTH_KEY", "wrong")

    def handler(request):
        return httpx.Response(401, json={"code": 6, "message": "credentials doesn't match db data"})

    with pytest.raises(visual.VisualizationFailed, match="Ключ авторизации"):
        visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(handler), sleep=no_sleep)


def test_pollinations_without_key(monkeypatch):
    monkeypatch.delenv("POLLINATIONS")
    seen = {}

    def handler(request: httpx.Request):
        seen["host"] = request.url.host
        seen["prompt"] = unquote(request.url.path.split("/prompt/", 1)[1])
        seen["params"] = dict(request.url.params)
        assert "Authorization" not in request.headers
        return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})

    picture = visual.generate(SUMMARY, "layer", OBJECTS, seed=7, transport=mock(handler), sleep=no_sleep)
    assert picture.provider == "pollinations"
    assert seen["host"] == "image.pollinations.ai"
    assert seen["prompt"] == picture.prompt and "bird's-eye" in picture.prompt
    assert seen["params"]["seed"] == "7" and seen["params"]["model"] == "flux"


def test_pollinations_with_key_and_rate_limit(monkeypatch):
    monkeypatch.delenv("POLLINATIONS")
    monkeypatch.setenv("POLLINATIONS_KEY", "sk_test")
    calls = []

    def handler(request: httpx.Request):
        calls.append(request.url.host)
        assert request.headers["Authorization"] == "Bearer sk_test"
        if len(calls) == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})

    picture = visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(handler), sleep=no_sleep)
    assert picture.mime == "image/png"
    assert calls == ["gen.pollinations.ai", "gen.pollinations.ai"]


def test_pollinations_rate_limit_gives_up(monkeypatch):
    monkeypatch.delenv("POLLINATIONS")
    with pytest.raises(visual.VisualizationFailed, match="15 секунд"):
        visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(lambda r: httpx.Response(429)), sleep=no_sleep)


def test_falls_back_to_next_provider(monkeypatch):
    monkeypatch.delenv("POLLINATIONS")
    monkeypatch.setenv("YANDEX_API_KEY", "AQVNkey")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "folder")

    def handler(request: httpx.Request):
        if request.url.host == "llm.api.cloud.yandex.net":
            return httpx.Response(403, json={"message": "Permission denied"})
        return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})

    picture = visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(handler), sleep=no_sleep)
    assert picture.provider == "pollinations"
    assert picture.meta["failed"] and picture.meta["failed"][0].startswith("YandexART: доступ запрещён")


def test_all_providers_fail_each_is_named(monkeypatch):
    monkeypatch.delenv("POLLINATIONS")
    monkeypatch.setenv("FUSIONBRAIN_KEY", "k")
    monkeypatch.setenv("FUSIONBRAIN_SECRET", "s")

    def handler(request):
        raise httpx.ConnectError("Name or service not known", request=request)

    with pytest.raises(visual.VisualizationFailed) as caught:
        visual.generate(SUMMARY, "layer", OBJECTS, transport=mock(handler), sleep=no_sleep)
    lines = str(caught.value).splitlines()
    assert lines[0].startswith("Kandinsky (Fusion Brain): нет связи с сервером (api-key.fusionbrain.ai)")
    assert lines[1].startswith("Pollinations: нет связи")


def test_provider_order(monkeypatch):
    monkeypatch.setenv("YANDEX_API_KEY", "AQVNkey")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "folder")
    monkeypatch.setenv("FUSIONBRAIN_KEY", "k")
    monkeypatch.setenv("FUSIONBRAIN_SECRET", "s")
    monkeypatch.setenv("GIGACHAT_AUTH_KEY", "abc")
    assert visual.providers() == ["yandexart", "gigachat", "kandinsky"]
    monkeypatch.setenv("GREENPLAN_AI_PROVIDER", "kandinsky, yandexart")
    assert visual.providers() == ["kandinsky", "yandexart"]
    assert visual.configured_provider() == "kandinsky"


def test_explicit_provider_without_key(monkeypatch):
    monkeypatch.setenv("GREENPLAN_AI_PROVIDER", "gigachat")
    state = visual.status()
    assert state["available"] is False
    assert "GIGACHAT_AUTH_KEY" in state["message"]
    with pytest.raises(visual.VisualizationUnavailable, match="GIGACHAT_AUTH_KEY"):
        visual.generate(SUMMARY, "layer", OBJECTS, provider="gigachat")


def test_check_command(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GIGACHAT_AUTH_KEY", "YWJjOmRlZg==")
    monkeypatch.setenv("YANDEX_API_KEY", "ajeabcdefghijklmnopq")
    monkeypatch.setenv("YANDEX_FOLDER_ID", "folder")
    code = visual.main(["--out", str(tmp_path)], transport=mock(gigachat_handler({})), sleep=no_sleep)
    output = capsys.readouterr().out
    assert code == 0
    assert "✗ YandexART" in output and "AQVN" in output
    assert "✓ GigaChat" in output
    assert (tmp_path / "check_gigachat.jpg").read_bytes() == JPEG
