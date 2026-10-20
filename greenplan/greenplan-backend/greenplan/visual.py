import argparse
import base64
import json
import os
import re
import ssl
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import certifi
import httpx

FUSIONBRAIN_URL = "https://api-key.fusionbrain.ai/key/api/v1"
YANDEX_URL = "https://llm.api.cloud.yandex.net"
YANDEX_IAM_URL = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
GIGACHAT_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_URLS = ("https://api.giga.chat/v1", "https://gigachat.devices.sberbank.ru/api/v1")
POLLINATIONS_URL = "https://image.pollinations.ai/prompt"
POLLINATIONS_KEY_URL = "https://gen.pollinations.ai/image"
TIMEOUT_S = 120.0
POLL_S = 3.0
POLLINATIONS_WAIT_S = 16.0

ORDER = ("yandexart", "gigachat", "kandinsky", "pollinations")
NAMES = {
    "yandexart": "YandexART",
    "gigachat": "GigaChat",
    "kandinsky": "Kandinsky (Fusion Brain)",
    "pollinations": "Pollinations",
}
KEYS = {
    "yandexart": "YANDEX_FOLDER_ID и YANDEX_API_KEY (или YANDEX_OAUTH_TOKEN, YANDEX_IAM_TOKEN)",
    "gigachat": "GIGACHAT_AUTH_KEY",
    "kandinsky": "FUSIONBRAIN_KEY и FUSIONBRAIN_SECRET",
}
OFF = {"0", "off", "false", "no", "нет"}
MIME = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}

TEXT = {
    "ru": {
        "seasons": {
            "summer": "солнечный летний день, сочная листва",
            "autumn": "ясный осенний день, жёлтая и оранжевая листва",
            "winter": "зимний день, деревья без листвы, снег на газонах",
        },
        "street": "озеленение городской улицы",
        "block": "благоустройство городского участка",
        "objects": {
            "ROAD": "проезжая часть с бортовым камнем",
            "PAVEMENT": "пешеходные тротуары и дорожки",
            "BUILDING": "жилые дома по краю участка",
            "LIGHTING": "опоры уличного освещения",
            "POWERLINE": "воздушная линия электропередачи на опорах",
            "POWERLINE_04KV": "воздушная линия электропередачи на опорах",
            "POWERLINE_6_10KV": "воздушная линия электропередачи на опорах",
            "POWERLINE_35KV": "высоковольтная линия электропередачи",
            "POWERLINE_110KV": "высоковольтная линия электропередачи",
            "MAF": "скамейки и малые архитектурные формы",
            "TRAM_TRACK": "трамвайные пути",
        },
        "intro": "Фотореалистичная архитектурная визуализация: {place} в Москве площадью {area}, "
                 "вид с высоты птичьего полёта под углом 45 градусов.",
        "plants": "Посажено {trees} лиственных деревьев с кронами 4–5 м, стоящих рядами с шагом около 10 м, "
                  "и {shrubs} кустарников группами между деревьями, ухоженный газон.",
        "hedges": "живые изгороди из подстриженного кустарника вдоль дорожек",
        "beds": "круглые цветники с яркими однолетниками",
        "elements": "Элементы сквера: {items}.",
        "site": "На участке: {items}. Деревья не стоят на проезжей части и тротуарах.",
        "finish": "{season}, мягкие тени, высокая детализация.",
        "ha": "га",
        "m2": "м²",
        "decimal": ",",
    },
    "en": {
        "seasons": {
            "summer": "sunny summer day, lush green foliage",
            "autumn": "clear autumn day, yellow and orange foliage",
            "winter": "winter day, bare trees, snow on the lawns",
        },
        "street": "a landscaped city street",
        "block": "a landscaped urban block",
        "objects": {
            "ROAD": "asphalt roadway with granite curbs",
            "PAVEMENT": "pedestrian sidewalks and paved paths",
            "BUILDING": "residential buildings along the edges",
            "LIGHTING": "street lamp posts",
            "POWERLINE": "overhead power line on poles",
            "POWERLINE_04KV": "overhead power line on poles",
            "POWERLINE_6_10KV": "overhead power line on poles",
            "POWERLINE_35KV": "high-voltage power line",
            "POWERLINE_110KV": "high-voltage power line",
            "MAF": "benches and small park furniture",
            "TRAM_TRACK": "tram tracks",
        },
        "intro": "Photorealistic architectural visualization, bird's-eye view at 45 degrees: {place} in Moscow, "
                 "{area}.",
        "plants": "{trees} deciduous trees with 4-5 m crowns planted in rows about 10 m apart, "
                  "{shrubs} shrubs in groups between the trees, well-kept lawn.",
        "hedges": "trimmed hedges along the paths",
        "beds": "round flower beds with bright annuals",
        "elements": "Park elements: {items}.",
        "site": "On site: {items}. No trees on the roadway or sidewalks.",
        "finish": "{season}, soft shadows, high detail, no text.",
        "ha": "ha",
        "m2": "m²",
        "decimal": ".",
    },
}

NEGATIVE = "текст, надписи, водяные знаки, логотипы, люди крупным планом, искажённая перспектива, мультяшный стиль"
GIGACHAT_SYSTEM = "Ты — художник‑визуализатор ландшафтных проектов. Рисуешь фотореалистичные изображения по описанию."
IMG_TAG = re.compile(r"<img[^>]*\bsrc=\"([^\"]+)\"")

_tokens: dict[tuple, tuple[str, float]] = {}


class VisualizationUnavailable(RuntimeError):
    pass


class VisualizationFailed(RuntimeError):
    pass


@dataclass
class Picture:
    image: bytes
    mime: str
    provider: str
    prompt: str
    elapsed_s: float = 0.0
    meta: dict = field(default_factory=dict)

    @property
    def extension(self) -> str:
        return MIME.get(self.mime, "jpg")

    def data_url(self) -> str:
        return f"data:{self.mime};base64,{base64.b64encode(self.image).decode()}"


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _area(area_m2: float, words: dict) -> str:
    if area_m2 >= 10_000:
        return f"{area_m2 / 10_000:.1f}".replace(".", words["decimal"]) + f" {words['ha']}"
    return f"{area_m2:,.0f}".replace(",", " ") + f" {words['m2']}"


def build_prompt(summary: dict, site_method: str, objects: list[str], season: str = "summer",
                 lang: str = "ru") -> str:
    words = TEXT.get(lang, TEXT["ru"])
    place = words["street"] if site_method == "corridor" else words["block"]
    phrases = []
    for kind in objects:
        phrase = words["objects"].get(kind)
        if phrase and phrase not in phrases:
            phrases.append(phrase)
    parts = [
        words["intro"].format(place=place, area=_area(summary.get("area_m2", 0), words)),
        words["plants"].format(trees=summary.get("trees", 0), shrubs=summary.get("shrubs", 0)),
    ]
    elements = []
    if summary.get("hedges_m"):
        elements.append(words["hedges"])
    if summary.get("flowerbeds"):
        elements.append(words["beds"])
    if elements:
        parts.append(words["elements"].format(items=", ".join(elements)))
    if phrases:
        parts.append(words["site"].format(items=", ".join(phrases)))
    parts.append(words["finish"].format(season=words["seasons"].get(season, words["seasons"]["summer"])))
    return " ".join(parts)[:1000]


def _yandex_ready() -> bool:
    return bool(_env("YANDEX_FOLDER_ID")) and any(
        _env(name) for name in ("YANDEX_API_KEY", "YANDEX_OAUTH_TOKEN", "YANDEX_IAM_TOKEN"))


READY = {
    "yandexart": _yandex_ready,
    "gigachat": lambda: bool(_env("GIGACHAT_AUTH_KEY") or _env("GIGACHAT_CREDENTIALS")),
    "kandinsky": lambda: bool(_env("FUSIONBRAIN_KEY") and _env("FUSIONBRAIN_SECRET")),
    "pollinations": lambda: _env("POLLINATIONS").lower() not in OFF,
}


def _wanted() -> list[str]:
    return [name.strip().lower() for name in _env("GREENPLAN_AI_PROVIDER").split(",") if name.strip()]


def _not_ready(name: str) -> str:
    if name == "pollinations":
        return "Pollinations выключен переменной POLLINATIONS=0"
    return f"{NAMES[name]}: не заданы {KEYS[name]}"


def providers() -> list[str]:
    order = _wanted() or list(ORDER)
    return [name for name in order if name in READY and READY[name]()]


def configured_provider() -> str | None:
    chain = providers()
    return chain[0] if chain else None


def status() -> dict:
    chain = providers()
    if not chain:
        wanted = [name for name in _wanted() if name in READY]
        if wanted:
            message = "Генераторы из GREENPLAN_AI_PROVIDER не настроены. " + "; ".join(map(_not_ready, wanted)) + "."
        else:
            message = ("Генератор изображений выключен. Задайте ключ YandexART, GigaChat или Kandinsky "
                       "либо уберите POLLINATIONS=0.")
    elif chain == ["pollinations"]:
        message = ("Ключи не заданы, картинку рисует Pollinations: без ключа не чаще раза в 15 секунд, "
                   "возможен водяной знак. Ключи YandexART, GigaChat или Kandinsky — в README.")
    else:
        message = None
    return {"available": bool(chain), "provider": chain[0] if chain else None, "providers": chain,
            "message": message}


def _client(transport=None, verify=True) -> httpx.Client:
    return httpx.Client(timeout=30.0, transport=transport, verify=verify)


def _reason(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:200].strip() or response.reason_phrase
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:200]
        for name in ("message", "error_description", "detail", "error"):
            if data.get(name):
                return str(data[name])[:200]
    return json.dumps(data, ensure_ascii=False)[:200]


def _kandinsky(prompt: str, client: httpx.Client, sleep, deadline: float, seed: int) -> tuple[bytes, dict]:
    base = (_env("FUSIONBRAIN_URL") or FUSIONBRAIN_URL).rstrip("/")
    headers = {"X-Key": f"Key {_env('FUSIONBRAIN_KEY')}", "X-Secret": f"Secret {_env('FUSIONBRAIN_SECRET')}"}
    params = {
        "type": "GENERATE",
        "numImages": 1,
        "width": 1024,
        "height": 640,
        "negativePromptDecoder": NEGATIVE,
        "generateParams": {"query": prompt},
    }

    pipelines = client.get(f"{base}/pipelines", headers=headers)
    if pipelines.status_code in (401, 403):
        raise VisualizationFailed(f"ключ не принят ({pipelines.status_code}): {_reason(pipelines)}")
    if pipelines.status_code == 200 and pipelines.json():
        pipeline_id = pipelines.json()[0]["id"]
        run = client.post(
            f"{base}/pipeline/run",
            headers=headers,
            files={"pipeline_id": (None, str(pipeline_id)), "params": (None, json.dumps(params), "application/json")},
        )
        status_url = f"{base}/pipeline/status/{{}}"
    else:
        models = client.get(f"{base}/models", headers=headers)
        if models.status_code != 200 or not models.json():
            raise VisualizationFailed(f"не удалось получить модель ({models.status_code})")
        model_id = models.json()[0]["id"]
        run = client.post(
            f"{base}/text2image/run",
            headers=headers,
            files={"model_id": (None, str(model_id)), "params": (None, json.dumps(params), "application/json")},
        )
        status_url = f"{base}/text2image/status/{{}}"

    if run.status_code not in (200, 201):
        raise VisualizationFailed(f"запрос отклонён ({run.status_code}): {_reason(run)}")
    started = run.json()
    task = started.get("uuid")
    if not task:
        raise VisualizationFailed(f"сервис недоступен: {started.get('status') or started.get('model_status')}")

    while time.monotonic() < deadline:
        sleep(POLL_S)
        data = client.get(status_url.format(task), headers=headers).json()
        state = data.get("status")
        if state == "DONE":
            result = data.get("result") or {}
            files = result.get("files") or data.get("images") or []
            if result.get("censored") or data.get("censored"):
                raise VisualizationFailed("изображение отфильтровано, попробуйте ещё раз")
            if not files:
                raise VisualizationFailed("пустой ответ")
            return base64.b64decode(files[0]), {"uuid": task}
        if state == "FAIL":
            raise VisualizationFailed(data.get("errorDescription") or "генерация не удалась")
    raise VisualizationFailed("не ответил вовремя")


def _yandex_headers(client: httpx.Client) -> dict:
    folder = _env("YANDEX_FOLDER_ID")
    key, oauth, iam = _env("YANDEX_API_KEY"), _env("YANDEX_OAUTH_TOKEN"), _env("YANDEX_IAM_TOKEN")
    if key.startswith("y0_") and not oauth:
        oauth, key = key, ""
    if key.startswith("t1.") and not iam:
        iam, key = key, ""
    if key.startswith("aje"):
        raise VisualizationFailed(
            "в YANDEX_API_KEY записан идентификатор ключа. Нужен сам секретный ключ — строка, которая "
            "начинается с AQVN; консоль показывает её один раз при создании ключа")
    if oauth and not iam:
        cached = _tokens.get(("yandex", oauth))
        if cached and cached[1] > time.time():
            iam = cached[0]
        else:
            response = client.post(YANDEX_IAM_URL, json={"yandexPassportOauthToken": oauth})
            if response.status_code != 200:
                raise VisualizationFailed(
                    f"OAuth‑токен не обменялся на IAM‑токен ({response.status_code}): {_reason(response)}")
            iam = response.json()["iamToken"]
            _tokens[("yandex", oauth)] = (iam, time.time() + 3600)
    headers = {"x-folder-id": folder}
    headers["Authorization"] = f"Bearer {iam}" if iam else f"Api-Key {key}"
    return headers


def _yandex_error(response: httpx.Response) -> str:
    code, reason = response.status_code, _reason(response)
    if code == 401:
        return (f"ключ не принят (401): {reason}. Нужен API‑ключ сервисного аккаунта с областью действия "
                "yc.ai.imageGeneration.execute, OAuth‑токен или IAM‑токен")
    if code == 403:
        return (f"доступ запрещён (403): {reason}. Проверьте роль ai.imageGeneration.user у сервисного "
                "аккаунта на этот каталог, что YANDEX_FOLDER_ID — идентификатор каталога, а не облака, "
                "и что платёжный аккаунт активен (пробный период подходит)")
    if code == 429:
        return "превышена квота запросов (429), подождите минуту"
    return f"запрос отклонён ({code}): {reason}"


def _yandexart(prompt: str, client: httpx.Client, sleep, deadline: float, seed: int) -> tuple[bytes, dict]:
    base = (_env("YANDEX_URL") or YANDEX_URL).rstrip("/")
    headers = _yandex_headers(client)
    body = {
        "modelUri": f"art://{_env('YANDEX_FOLDER_ID')}/yandex-art/latest",
        "generationOptions": {"seed": str(seed), "aspectRatio": {"widthRatio": "16", "heightRatio": "10"}},
        "messages": [{"weight": "1", "text": prompt}],
    }
    run = client.post(f"{base}/foundationModels/v1/imageGenerationAsync", headers=headers, json=body)
    if run.status_code != 200:
        raise VisualizationFailed(_yandex_error(run))
    operation = run.json()["id"]
    while time.monotonic() < deadline:
        sleep(POLL_S)
        response = client.get(f"{base}/operations/{operation}", headers=headers)
        if response.status_code != 200:
            raise VisualizationFailed(_yandex_error(response))
        data = response.json()
        if not data.get("done"):
            continue
        if data.get("error"):
            raise VisualizationFailed(data["error"].get("message") or "генерация не удалась")
        return base64.b64decode(data["response"]["image"]), {"operation": operation}
    raise VisualizationFailed("не ответил вовремя")


def _gigachat_verify():
    bundle = _env("GIGACHAT_CA_BUNDLE")
    if bundle:
        context = ssl.create_default_context(cafile=certifi.where())
        context.load_verify_locations(cafile=bundle)
        return context
    return _env("GIGACHAT_VERIFY_SSL").lower() not in OFF


def _gigachat_identity() -> tuple[str, str, str]:
    key = (_env("GIGACHAT_AUTH_KEY") or _env("GIGACHAT_CREDENTIALS")).removeprefix("Basic ").strip()
    return "gigachat", key, _env("GIGACHAT_SCOPE") or "GIGACHAT_API_PERS"


def _gigachat_token(client: httpx.Client) -> str:
    identity = _gigachat_identity()
    _, key, scope = identity
    cached = _tokens.get(identity)
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    response = client.post(
        _env("GIGACHAT_AUTH_URL") or GIGACHAT_AUTH_URL,
        headers={
            "Authorization": f"Basic {key}",
            "RqUID": str(uuid.uuid4()),
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"scope": scope},
    )
    if response.status_code in (400, 401):
        raise VisualizationFailed(
            f"ключ авторизации не принят ({response.status_code}): {_reason(response)}. В GIGACHAT_AUTH_KEY нужен "
            "«Ключ авторизации» из личного кабинета developers.sber.ru; GIGACHAT_SCOPE для физлиц — "
            "GIGACHAT_API_PERS, для ИП и компаний — GIGACHAT_API_B2B или GIGACHAT_API_CORP")
    if response.status_code != 200:
        raise VisualizationFailed(f"токен не выдан ({response.status_code}): {_reason(response)}")
    data = response.json()
    expires = data.get("expires_at", 0) / 1000 or time.time() + 1500
    _tokens[identity] = (data["access_token"], expires)
    return data["access_token"]


def _gigachat(prompt: str, client: httpx.Client, sleep, deadline: float, seed: int) -> tuple[bytes, dict]:
    token = _gigachat_token(client)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    body = {
        "model": _env("GIGACHAT_MODEL") or "GigaChat",
        "messages": [
            {"role": "system", "content": GIGACHAT_SYSTEM},
            {"role": "user", "content": f"Нарисуй картинку. {prompt}"},
        ],
        "function_call": "auto",
    }
    bases = [_env("GIGACHAT_URL").rstrip("/")] if _env("GIGACHAT_URL") else list(GIGACHAT_URLS)
    timeout = httpx.Timeout(max(deadline - time.monotonic(), 10.0), connect=15.0)
    failure: Exception | None = None
    for base in bases:
        try:
            response = client.post(f"{base}/chat/completions", headers=headers, json=body, timeout=timeout)
        except httpx.ConnectError as error:
            if "CERTIFICATE" in str(error).upper():
                raise
            failure = error
            continue
        if response.status_code == 404:
            failure = VisualizationFailed(f"адрес {base} не найден (404)")
            continue
        break
    else:
        raise failure
    if response.status_code == 401:
        _tokens.pop(_gigachat_identity(), None)
        raise VisualizationFailed(f"токен не принят (401): {_reason(response)}")
    if response.status_code == 402:
        raise VisualizationFailed("закончились токены на тарифе (402)")
    if response.status_code == 429:
        raise VisualizationFailed("слишком много запросов (429), подождите минуту")
    if response.status_code != 200:
        raise VisualizationFailed(f"запрос отклонён ({response.status_code}): {_reason(response)}")
    content = response.json()["choices"][0]["message"].get("content") or ""
    found = IMG_TAG.search(content)
    if not found:
        raise VisualizationFailed(f"ответил текстом вместо картинки: «{content[:160].strip()}»")
    file_id = found.group(1)
    image = client.get(f"{base}/files/{file_id}/content",
                       headers={"Authorization": f"Bearer {token}", "Accept": "application/jpg"})
    if image.status_code != 200:
        raise VisualizationFailed(f"картинка не скачалась ({image.status_code}): {_reason(image)}")
    return image.content, {"file_id": file_id}


def _pollinations(prompt: str, client: httpx.Client, sleep, deadline: float, seed: int) -> tuple[bytes, dict]:
    key = _env("POLLINATIONS_KEY")
    model = _env("POLLINATIONS_MODEL") or "flux"
    params = {"width": 1024, "height": 640, "seed": seed, "model": model, "nologo": "true"}
    if key:
        url = f"{(_env('POLLINATIONS_URL') or POLLINATIONS_KEY_URL).rstrip('/')}/{quote(prompt, safe='')}"
        headers = {"Authorization": f"Bearer {key}"}
    else:
        url = f"{(_env('POLLINATIONS_URL') or POLLINATIONS_URL).rstrip('/')}/{quote(prompt, safe='')}"
        headers = {}
    for attempt in range(3):
        timeout = httpx.Timeout(max(deadline - time.monotonic(), 10.0), connect=15.0)
        response = client.get(url, params=params, headers=headers, timeout=timeout, follow_redirects=True)
        if response.status_code != 429 or attempt == 2 or time.monotonic() + POLLINATIONS_WAIT_S > deadline:
            break
        sleep(POLLINATIONS_WAIT_S)
    if response.status_code == 429:
        raise VisualizationFailed("слишком частые запросы: без ключа не чаще раза в 15 секунд")
    if response.status_code in (401, 402, 403):
        raise VisualizationFailed(
            f"сервис просит ключ ({response.status_code}): {_reason(response)}. Ключ выдают на "
            "enter.pollinations.ai, переменная POLLINATIONS_KEY")
    if response.status_code != 200:
        raise VisualizationFailed(f"ошибка сервиса ({response.status_code}): {_reason(response)}")
    if not response.headers.get("content-type", "").startswith("image/"):
        raise VisualizationFailed("вместо изображения пришёл другой ответ")
    return response.content, {"model": model}


RUNNERS = {
    "yandexart": _yandexart,
    "gigachat": _gigachat,
    "kandinsky": _kandinsky,
    "pollinations": _pollinations,
}


def _network_error(provider: str, error: httpx.HTTPError) -> str:
    text = str(error)
    if "CERTIFICATE" in text.upper():
        if provider == "gigachat":
            return ("сертификат сервера Сбера не прошёл проверку. Установите корневой сертификат Минцифры "
                    "(russian_trusted_root_ca) и укажите путь к нему в GIGACHAT_CA_BUNDLE или задайте "
                    "GIGACHAT_VERIFY_SSL=0")
        return f"сертификат сервера не прошёл проверку: {text[:160]}"
    if isinstance(error, httpx.TimeoutException):
        return "сервер не ответил вовремя"
    try:
        host = error.request.url.host
    except RuntimeError:
        host = ""
    where = f" ({host})" if host else ""
    return f"нет связи с сервером{where}: проверьте интернет, VPN или прокси"


def _mime(image: bytes) -> str:
    if image[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def generate(summary: dict, site_method: str, objects: list[str], season: str = "summer",
             seed: int | None = None, provider: str | None = None, transport=None,
             sleep=time.sleep) -> Picture:
    if provider:
        if provider not in READY:
            raise VisualizationUnavailable(f"Неизвестный генератор: {provider}")
        if not READY[provider]():
            raise VisualizationUnavailable(_not_ready(provider))
        chain = [provider]
    else:
        chain = providers()
    if not chain:
        raise VisualizationUnavailable(status()["message"])
    seed = seed if seed is not None else int(time.time()) % 1_000_000
    timeout = float(_env("GREENPLAN_AI_TIMEOUT") or TIMEOUT_S)
    errors = []
    for name in chain:
        prompt = build_prompt(summary, site_method, objects, season, "en" if name == "pollinations" else "ru")
        started = time.monotonic()
        try:
            verify = _gigachat_verify() if name == "gigachat" else True
        except (OSError, ssl.SSLError) as error:
            errors.append(f"{NAMES[name]}: не удалось прочитать сертификат из GIGACHAT_CA_BUNDLE ({error})")
            continue
        try:
            with _client(transport, verify) as client:
                image, meta = RUNNERS[name](prompt, client, sleep, started + timeout, seed)
        except VisualizationFailed as error:
            errors.append(f"{NAMES[name]}: {error}")
            continue
        except httpx.HTTPError as error:
            errors.append(f"{NAMES[name]}: {_network_error(name, error)}")
            continue
        if not image:
            errors.append(f"{NAMES[name]}: пустой ответ")
            continue
        return Picture(image=image, mime=_mime(image), provider=name, prompt=prompt,
                       elapsed_s=round(time.monotonic() - started, 1), meta={**meta, "failed": errors})
    raise VisualizationFailed("\n".join(errors))


CHECK_SUMMARY = {"trees": 120, "shrubs": 640, "area_m2": 15_000, "hedges_m": 300, "flowerbeds": 3}
CHECK_OBJECTS = ["ROAD", "PAVEMENT", "BUILDING", "LIGHTING", "MAF"]


def main(argv: list[str] | None = None, transport=None, sleep=time.sleep) -> int:
    parser = argparse.ArgumentParser(prog="python -m greenplan.visual",
                                     description="Проверка генераторов изображений: каждый настроенный рисует "
                                                 "тестовый участок, картинки сохраняются в папку.")
    parser.add_argument("providers", nargs="*", metavar="генератор",
                        help="yandexart, gigachat, kandinsky, pollinations; по умолчанию все настроенные")
    parser.add_argument("--out", default=".", help="куда сохранить картинки")
    args = parser.parse_args(argv)
    unknown = [name for name in args.providers if name not in READY]
    if unknown:
        parser.error(f"неизвестный генератор: {', '.join(unknown)}")
    chain = args.providers or providers()
    if not chain:
        print(status()["message"])
        return 1
    worked = 0
    for name in chain:
        try:
            picture = generate(CHECK_SUMMARY, "layer", CHECK_OBJECTS, provider=name, transport=transport, sleep=sleep)
        except (VisualizationFailed, VisualizationUnavailable) as error:
            print(f"✗ {error}")
            continue
        path = Path(args.out) / f"check_{name}.{picture.extension}"
        path.write_bytes(picture.image)
        print(f"✓ {NAMES[name]}: {picture.elapsed_s} с, {path}")
        worked += 1
    return 0 if worked else 1


if __name__ == "__main__":
    sys.exit(main())
