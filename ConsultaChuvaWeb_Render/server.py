#!/usr/bin/env python3
"""Servidor local e proxy para a API legada da ANA. Apenas biblioteca padrão."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from xml.etree import ElementTree as ET
from datetime import datetime, date
import json, os, socket

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8765"))
HOST = os.environ.get("HOST", "0.0.0.0")
# A documentação atual da operação legada está publicada neste host.
# O host antigo fica como fallback, pois a disponibilidade pode variar.
ANA_ENDPOINTS = [
    "https://www.ana.gov.br/telemetria1ws/ServiceANA.asmx/DadosHidrometeorologicos",
    "https://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos",
]
ANA_TIMEOUT = 9

def local_name(tag):
    return tag.rsplit("}", 1)[-1].split(":")[-1].lower()

def parse_date(value):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt).date()
        except ValueError:
            pass
    return None

def parse_datetime(value):
    value = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
                "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            pass
    return None

def parse_xml(raw, station):
    """Interpreta DataTable/XML com ou sem namespace e nomes de campos comuns."""
    root = ET.fromstring(raw)
    # Algumas respostas SOAP podem encapsular o XML da tabela como texto.
    for el in list(root.iter()):
        if local_name(el.tag).endswith("result") and el.text and el.text.lstrip().startswith("<"):
            try:
                return parse_xml(el.text.encode("utf-8"), station)
            except ET.ParseError:
                pass

    date_names = {"datahora", "data_hora", "data", "datamedicao", "dataregistro", "datetime"}
    rain_names = {"chuva", "precipitacao", "precipitação", "pluviometria", "valorchuva", "chuvaacumulada"}
    station_names = {"codestacao", "codigoestacao", "estacao", "codigo"}

    rows, seen = [], set()
    for rec in root.iter():
        children = list(rec)
        if not children:
            continue
        values = {local_name(c.tag): (c.text or "").strip() for c in children}
        date_key = next((k for k in date_names if values.get(k)), None)
        rain_key = next((k for k in rain_names if k in values), None)
        if not date_key or not rain_key:
            continue
        parsed = parse_datetime(values[date_key])
        if not parsed:
            continue
        raw_rain = values.get(rain_key, "")
        try:
            amount = float(raw_rain.replace(",", ".")) if raw_rain not in ("", "-", "null", "None") else None
        except ValueError:
            amount = None
        code = next((values[k] for k in station_names if values.get(k)), station)
        key = (code, parsed.isoformat(), amount)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "station": code,
            "date": parsed.strftime("%Y-%m-%d"),
            "dateDisplay": parsed.strftime("%d/%m/%Y"),
            "time": parsed.strftime("%H:%M"),
            "rain": amount
        })
    return rows

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def log_message(self, fmt, *args):
        print("[web]", fmt % args)

    def send_json(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path != "/api/consulta":
            return super().do_GET()
        qs = parse_qs(parsed_url.query)
        station = (qs.get("estacao") or [""])[0].strip()
        start = parse_date((qs.get("inicio") or [""])[0])
        end = parse_date((qs.get("fim") or [""])[0])
        today = date.today()

        if not station.isdigit() or not (1 <= len(station) <= 10):
            return self.send_json(400, {"error": "Informe um código de estação válido, usando apenas números."})
        if not start or not end or start > end:
            return self.send_json(400, {"error": "Confira as datas informadas."})
        if end > today:
            return self.send_json(200, {"rows": [], "empty": True,
                "message": "data nao constaa nos dados ou ainda nao tem previsão desses dados"})

        # Os nomes dos parâmetros seguem a documentação oficial da operação:
        # codEstacao, dataInicio e dataFim.
        params = urlencode({
            "codEstacao": station,
            "dataInicio": start.strftime("%d/%m/%Y"),
            "dataFim": end.strftime("%d/%m/%Y")
        })
        last_error = None
        for endpoint in ANA_ENDPOINTS:
            try:
                request = Request(endpoint + "?" + params, headers={
                    "User-Agent": "Mozilla/5.0 (compatible; PluviaAcademic/1.1)",
                    "Accept": "text/xml, application/xml, */*"
                })
                with urlopen(request, timeout=ANA_TIMEOUT) as response:
                    raw = response.read(8_000_000)
                rows = parse_xml(raw, station)
                rows = [r for r in rows if start.isoformat() <= r["date"] <= end.isoformat()]
                rows.sort(key=lambda r: (r["date"], r["time"]))
                if rows:
                    return self.send_json(200, {"rows": rows, "empty": False})
                # Uma resposta XML válida sem registros não deve ser tratada como falha de conexão.
                return self.send_json(200, {"rows": [], "empty": True,
                    "message": "data nao constaa nos dados ou ainda nao tem previsão desses dados"})
            except (TimeoutError, socket.timeout) as exc:
                last_error = "timeout"
            except HTTPError as exc:
                last_error = f"http_{exc.code}"
            except URLError:
                last_error = "connection"
            except ET.ParseError:
                last_error = "xml"
            except Exception:
                last_error = "unexpected"

        if last_error == "timeout":
            return self.send_json(504, {"error": "O serviço da ANA demorou para responder nos endereços testados. Tente novamente mais tarde."})
        if last_error and last_error.startswith("http_"):
            return self.send_json(502, {"error": "O serviço da ANA recusou a consulta nos endereços testados. Tente novamente mais tarde."})
        if last_error == "connection":
            return self.send_json(502, {"error": "Não foi possível conectar ao serviço da ANA. Verifique a conexão e tente novamente."})
        if last_error == "xml":
            return self.send_json(502, {"error": "A ANA respondeu em um formato inesperado. O formato retornado não pôde ser interpretado."})
        return self.send_json(500, {"error": "Ocorreu um erro inesperado durante a consulta."})

if __name__ == "__main__":
    os.chdir(ROOT)
    print(f"Pluvia iniciado em {HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
