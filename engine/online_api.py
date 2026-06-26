# -*- coding: utf-8 -*-
import urllib.request
import urllib.parse
import json


def translate_google(text: str, from_lang: str, to_lang: str) -> str:
    sl = "en" if from_lang.startswith("en") else "zh-CN"
    tl = "zh-CN" if from_lang.startswith("en") else "en"
    url = "https://translate.googleapis.com/translate_a/single"
    query_string = urllib.parse.urlencode({'client': 'gtx', 'sl': sl, 'tl': tl, 'dt': 't', 'q': text})
    req = urllib.request.Request(f"{url}?{query_string}", headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5) as response:
        data = json.loads(response.read().decode('utf-8'))
        translated_segments = []
        if data and isinstance(data, list) and len(data) > 0:
            for segment in data[0]:
                if isinstance(segment, list) and len(segment) > 0:
                    translated_segments.append(segment[0])
        return "".join(translated_segments)


def translate_mymemory(text: str, from_lang: str, to_lang: str) -> str:
    if len(text) <= 500:
        return _translate_mymemory_single(text, from_lang, to_lang)
    paragraphs = text.split("\n")
    chunks, current_chunk, current_len = [], [], 0
    for p in paragraphs:
        if current_len + len(p) + 1 > 450:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_chunk, current_len = [p], len(p)
        else:
            current_chunk.append(p)
            current_len += len(p) + 1
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    translated_chunks = []
    for chunk in chunks:
        if chunk.strip():
            translated_chunks.append(_translate_mymemory_single(chunk, from_lang, to_lang))
        else:
            translated_chunks.append("")
    return "\n".join(translated_chunks)


def _translate_mymemory_single(text: str, from_lang: str, to_lang: str) -> str:
    f = "en" if from_lang.startswith("en") else "zh"
    t = "zh" if from_lang.startswith("zh") else "en"
    url = "https://api.mymemory.translated.net/get"
    query_string = urllib.parse.urlencode({"q": text, "langpair": f"{f}|{t}"})
    req = urllib.request.Request(f"{url}?{query_string}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=5) as response:
        res_json = json.loads(response.read().decode("utf-8"))
        if "responseData" in res_json:
            return res_json["responseData"].get("translatedText", text)
        raise ValueError(f"MyMemory 异常: {res_json}")


def translate_online_with_fallback(text: str, from_lang: str, to_lang: str) -> str:
    try:
        return translate_google(text, from_lang, to_lang)
    except Exception:
        pass
    try:
        return translate_mymemory(text, from_lang, to_lang)
    except Exception as e_mymemory:
        return f"[翻译接口错误] 在线链路均无法建立连接。网络超时或被阻断。最后反馈: {e_mymemory}"
