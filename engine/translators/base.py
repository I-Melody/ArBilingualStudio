# -*- coding: utf-8 -*-
import json
import urllib.request
import logging

HTTP_TIMEOUT = 10
OLLAMA_BASE = "http://localhost:11434"


def make_local_request(url: str, data_dict=None, timeout: int = HTTP_TIMEOUT) -> str:
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)
    req = urllib.request.Request(url)
    if data_dict:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data_dict).encode("utf-8")
        req.method = "POST"
    with opener.open(req, timeout=timeout) as response:
        return response.read().decode("utf-8")


def suppress_noisy_loggers():
    for noisy_logger in ["argostranslate", "stanza", "transformers", "urllib3"]:
        logging.getLogger(noisy_logger).setLevel(logging.ERROR)
